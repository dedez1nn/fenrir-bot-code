import asyncio
import logging
import os
import traceback

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from db import (
    apply_migrations,
    close_pool,
    import_legacy_json,
    init_pool,
    load_server_config,
    refresh_server_config,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("fenrir")

# Guild principal — lido do .env para evitar literal no código-fonte.
GUILD_ID = int(os.getenv("GUILD_ID", "1426202696955986022"))


def _module_defines_setup(path: str) -> bool:
    """Heurística leve: detecta se um arquivo tem `setup` exportado.

    Lê o source sem importar. Suficiente para distinguir pacotes-cog (com
    `async def setup(bot)`) de `__init__.py` vazios.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return False
    return "def setup(" in src


class FenrirBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        # Atributos populados em setup_hook; cogs devem checar `is not None`.
        self.db = None
        self.config = None

    async def _init_database(self) -> None:
        """Inicializa pool, aplica migrations e importa JSONs se necessário.

        Tolerante a falha: se o Postgres não estiver disponível, loga aviso e
        continua. Cogs que ainda usam JSON seguem operando normalmente.
        """
        self.db = await init_pool()
        if self.db is None:
            log.warning("Postgres indisponível — bot operando em modo legado (JSON).")
            return

        try:
            await apply_migrations(self.db)
        except Exception as exc:
            log.error("Falha ao aplicar migrations: %s", exc)
            return

        try:
            counters = await import_legacy_json(self.db)
            if any(counters.values()):
                log.info("Importação JSON→DB concluída: %s", counters)
        except Exception as exc:
            log.error("Falha ao importar JSONs legados: %s", exc)

        self.config = await load_server_config(self.db, GUILD_ID)
        if self.config is None:
            log.warning("server_config não carregada para guild %s.", GUILD_ID)
        else:
            log.info("server_config carregada (guild %s).", GUILD_ID)

    async def reload_config(self) -> None:
        """Recarrega `bot.config` a partir do banco. Chamado pela API ao salvar."""
        if self.db is None:
            return
        guild_id = self.config.guild_id if self.config else GUILD_ID
        self.config = await refresh_server_config(self.db, guild_id)

    async def guard_channel(self, interaction: discord.Interaction) -> bool:
        """Verifica se o comando foi enviado no canal de comandos correto.

        Retorna True (e responde com erro ephemeral) se o canal estiver errado.
        Retorna False se o comando deve prosseguir.
        Administradores passam sempre. Se config não estiver carregada, passa.
        """
        if interaction.user.guild_permissions.administrator:
            return False
        cfg = self.config
        if cfg is None:
            return False
        cmd_ch_id = cfg.get("commands_channel_id")
        if cmd_ch_id is None:
            return False
        if interaction.channel.id == cmd_ch_id:
            return False
        ch = self.get_channel(cmd_ch_id)
        mention = ch.mention if ch else f"<#{cmd_ch_id}>"
        await interaction.response.send_message(
            f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {mention} !",
            ephemeral=True,
        )
        return True

    async def setup_hook(self):
        await self._init_database()

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        COGS_DIR = os.path.join(BASE_DIR, "cogs")

        for root, dirs, files in os.walk(COGS_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            # Pacotes com setup() no __init__.py (ex.: cogs.antispam) são
            # carregados como uma única extensão; submódulos não são entry points.
            init_path = os.path.join(root, "__init__.py")
            if os.path.exists(init_path) and _module_defines_setup(init_path):
                rel = os.path.relpath(root, BASE_DIR)
                module = rel.replace(os.sep, ".")
                await self.load_extension(module)
                dirs[:] = []  # não recursar — submódulos já vêm pelo pacote
                continue

            for filename in files:
                if filename.endswith(".py") and filename != "__init__.py":
                    rel = os.path.relpath(os.path.join(root, filename), BASE_DIR)
                    module = rel.replace(os.sep, ".")[:-3]
                    await self.load_extension(module)

        await self.tree.sync()
        log.info("Bot setup loaded")

    async def close(self) -> None:
        try:
            await close_pool()
        finally:
            await super().close()

    def _cfg_channel(self, key: str):
        """Resolve um canal via server_config. Retorna None se config/canal indisponível."""
        if self.config is None:
            return None
        ch_id = self.config.get(key)
        return self.get_channel(ch_id) if ch_id else None

    async def on_ready(self):
        log.info("🤖 Bot conectado como %s (ID: %s)", self.user, self.user.id)

        await self.change_presence(
            activity=discord.Streaming(
                name='Relaxando na Alcateia do Fenrir 🐺',
                url='https://www.twitch.tv/discord'
            )
        )

        status_cog = self.get_cog("StatusCog")
        if status_cog:
            canal_status = self._cfg_channel("status_channel_id")
            if canal_status:
                async for message in canal_status.history(limit=10):
                    if message.author == self.user:
                        await message.delete()
                        await asyncio.sleep(0.5)
                await status_cog.status(canal_status)

        cores_cog = self.get_cog("EnviarCores")
        if cores_cog:
            canal_cores = self._cfg_channel("colors_channel_id")
            if canal_cores:
                async for message in canal_cores.history(limit=10):
                    if message.author == self.user:
                        await message.delete()
                        await asyncio.sleep(0.5)
                await cores_cog.cores(canal_cores)

        pix_cog = self.get_cog("PixCog")
        if pix_cog:
            canal_pix = self._cfg_channel("pix_channel_id")
            if canal_pix:
                async for message in canal_pix.history(limit=10):
                    if message.author == self.user:
                        await message.delete()
                        await asyncio.sleep(0.5)
                await pix_cog.setup_planos_embed(canal_pix)

        ticket_cog = self.get_cog("TicketCog")
        if ticket_cog:
            canal_ticket = self._cfg_channel("tickets_channel_id")
            if canal_ticket:
                async for message in canal_ticket.history(limit=10):
                    if message.author == self.user:
                        await message.delete()
                        await asyncio.sleep(0.5)
                await ticket_cog.ticket(canal_ticket)


bot = FenrirBot()


@bot.tree.command(name="ping", description="Mostra a latência do bot")
async def ping(interaction: discord.Interaction):
    if await bot.guard_channel(interaction):
        return

    latencia = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência: **{latencia}ms**",
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    traceback.print_exception(type(error), error, error.__traceback__)
    msg = "❌ Ocorreu um erro inesperado. Tente novamente mais tarde."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


load_dotenv()
TOKEN = os.getenv("TOKEN")


async def main():
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
