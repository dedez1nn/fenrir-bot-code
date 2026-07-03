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
    load_global_config,
    load_server_config,
    refresh_server_config,
    set_config_ttl,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("fenrir")

# Guild principal — lido do .env para evitar literal no código-fonte.
GUILD_ID = int(os.getenv("GUILD_ID", "1426202696955986022"))

# Mapeia feature key → nome da cog para dispatcher do NOTIFY feature:{guild_id}:{feature}.
_FEATURE_COG_MAP: dict[str, str] = {
    "tickets":         "TicketCog",
    "voice_creator":   "VoiceCreator",
    "member_logs":     "MemberLogs",
    "colors":          "EnviarCores",
    "adventures":      "AventuraCog",
    "guilds":          "GuildSystem",
    "guild_raids":     "GuildAllianceRaidSystem",
    "antispam":        "AntiSpam",
    "antinuke":        "AntiNuke",
    "invite_blocker":  "InviteBlocker",
    "auto_remove_bots":"AutoRemoveBots",
    "xp":              "XPCog",
    "economy":         "FenrirCoins",
    "premium":         "PixCog",
    "riot":            "RiotCog",
    "steam":           "SteamCog",
    "gnews":           "GNewsCog",
}


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
        self.global_config = None
        # Callback armazenado para poder remover o listener no shutdown
        self._cache_notify_cb = None

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

        self.global_config = await load_global_config(self.db)
        ttl = self.global_config.get("server_config_ttl_s", 300)
        set_config_ttl(ttl)
        log.info("global_config carregada (TTL=%ss).", ttl)

        guild_id = self.global_config.get("primary_guild_id") or GUILD_ID
        self.config = await load_server_config(self.db, guild_id)
        if self.config is None:
            log.warning("server_config não carregada para guild %s.", guild_id)
        else:
            log.info("server_config carregada (guild %s).", guild_id)

    async def reload_config(self) -> None:
        """Recarrega `bot.config` a partir do banco. Chamado pela API ao salvar."""
        if self.db is None:
            return
        gc = self.global_config
        guild_id = (gc.get("primary_guild_id") if gc else None) or GUILD_ID
        if self.config:
            guild_id = self.config.get("guild_id") or guild_id
        self.config = await refresh_server_config(self.db, guild_id)

    # ─── LISTEN/NOTIFY (cache invalidation) ───────────────────────────────────

    async def _start_cache_listener(self) -> None:
        """Registra listener PostgreSQL NOTIFY no canal `fenrir_cache`.

        Payloads suportados:
          - `user:{id}`                    — recarrega dados do usuário nos cogs
          - `premium:{id}:{plan}`          — recarrega + concede role/coins/xp
          - `config:{guild_id}`            — recarrega server_config
          - `antispam:{guild_id}`          — recarrega config do antispam no cog
          - `antinuke:{guild_id}`          — recarrega config do antinuke no cog
          - `feature:{guild_id}:{feature}` — recarrega feature flag na cog afetada
        """
        if self.db is None:
            return

        async def _listen_loop():
            conn = None
            try:
                conn = await self.db.acquire()
                def _on_notify(conn, pid, channel, payload):
                    asyncio.create_task(self._handle_cache_notification(payload))

                await conn.add_listener("fenrir_cache", _on_notify)
                log.info("Cache listener ativo (LISTEN fenrir_cache).")

                while True:
                    await asyncio.sleep(300)
            except Exception as exc:
                log.warning("Falha ao iniciar cache listener: %s", exc)
            finally:
                if conn:
                    await self.db.release(conn)

        asyncio.create_task(_listen_loop())

    async def _handle_cache_notification(self, payload: str) -> None:
        """Despacha notificação de invalidação de cache."""
        try:
            kind, value = payload.split(":", 1)
        except ValueError:
            log.warning("Payload NOTIFY inválido: %r", payload)
            return

        if kind == "user":
            await self._invalidate_user_cache(int(value))

        elif kind == "premium":
            # value = "{user_id}:{plano}"
            parts = value.split(":", 1)
            uid   = int(parts[0])
            plano = parts[1] if len(parts) > 1 else None
            await self._invalidate_user_cache(uid)
            if plano:
                pix_cog = self.get_cog("PixCog")
                if pix_cog and hasattr(pix_cog, "grant_premium_rewards"):
                    try:
                        await pix_cog.grant_premium_rewards(uid, plano)
                    except Exception as exc:
                        log.warning("grant_premium_rewards falhou para %s/%s: %s", uid, plano, exc)

        elif kind == "config":
            await self.reload_config()
            await self._check_config_health()
            xp_cog = self.get_cog("XPCog")
            if xp_cog and hasattr(xp_cog, "_carregar_cargos_por_nivel"):
                xp_cog.cargos_por_nivel = xp_cog._carregar_cargos_por_nivel()

        elif kind == "antispam":
            cog = self.get_cog("AntiSpam")
            if cog and hasattr(cog, "reload_config_from_db"):
                try:
                    await cog.reload_config_from_db()
                except Exception as exc:
                    log.warning("AntiSpam.reload_config_from_db falhou: %s", exc)

        elif kind == "antinuke":
            cog = self.get_cog("AntiNuke")
            if cog and hasattr(cog, "reload_config_from_db"):
                try:
                    await cog.reload_config_from_db()
                except Exception as exc:
                    log.warning("AntiNuke.reload_config_from_db falhou: %s", exc)

        elif kind == "feature":
            # value = "{guild_id}:{feature}"
            parts = value.split(":", 1)
            if len(parts) == 2:
                feature_name = parts[1]
                cog_name = _FEATURE_COG_MAP.get(feature_name)
                if cog_name:
                    cog = self.get_cog(cog_name)
                    if cog and hasattr(cog, "reload_feature_state"):
                        try:
                            await cog.reload_feature_state()
                        except Exception as exc:
                            log.warning("reload_feature_state falhou para %s/%s: %s", cog_name, feature_name, exc)

    async def _invalidate_user_cache(self, user_id: int) -> None:
        """Recarrega dados de um usuário do DB para os caches em memória."""
        if self.db is None:
            return
        from repositories import users as users_repo

        try:
            row = await users_repo.get(self.db, user_id)
            if row is None:
                return
            cached = users_repo.row_to_cache(row)
            uid_str = str(user_id)
            for cog_name in ("FenrirCoins", "XPCog"):
                cog = self.get_cog(cog_name)
                if cog and hasattr(cog, "user_data") and uid_str in cog.user_data:
                    cog.user_data[uid_str].update(cached)
        except Exception as exc:
            log.warning("Falha ao invalidar cache do usuário %s: %s", user_id, exc)

    async def _check_config_health(self) -> None:
        """Roda validate_all contra server_config e loga warnings por feature com erros."""
        if self.config is None:
            return
        try:
            from db.validators import validate_all
            all_errors = validate_all(self.config.to_dict())
            for feature, errors in all_errors.items():
                for err in errors:
                    log.warning(
                        "Config inválida [%s / %s]: %s — %s",
                        feature, err.get("field"), err.get("code"), err.get("message"),
                    )
            ok = [f for f, e in all_errors.items() if not e]
            bad = [f for f, e in all_errors.items() if e]
            if bad:
                log.warning("Features com config incompleta: %s", bad)
            else:
                log.info("Config health OK — todas as %d features válidas.", len(ok))
        except Exception as exc:
            log.warning("Falha ao verificar saúde da config: %s", exc)

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

    async def _safe_load_extension(self, module: str) -> None:
        """Carrega uma extensão isolando falhas.

        Uma cog quebrada (import faltando, dependência externa indisponível)
        loga o erro mas não impede o carregamento das demais nem derruba o boot.
        """
        try:
            await self.load_extension(module)
        except Exception:
            log.error("Falha ao carregar a cog '%s':\n%s", module, traceback.format_exc())

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
                await self._safe_load_extension(module)
                dirs[:] = []  # não recursar — submódulos já vêm pelo pacote
                continue

            for filename in files:
                if filename.endswith(".py") and filename != "__init__.py":
                    rel = os.path.relpath(os.path.join(root, filename), BASE_DIR)
                    module = rel.replace(os.sep, ".")[:-3]
                    await self._safe_load_extension(module)

        await self.tree.sync()
        await self._start_cache_listener()
        log.info("Bot setup loaded")

    async def close(self) -> None:
        if self.db is not None and self._cache_notify_cb is not None:
            try:
                await self.db.remove_listener("fenrir_cache", self._cache_notify_cb)
            except Exception:
                pass
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
        await self._check_config_health()

        await self.change_presence(
            activity=discord.Streaming(
                name='Relaxando na Alcateia do Fenrir 🐺',
                url='https://www.twitch.tv/discord'
            )
        )

        status_cog = self.get_cog("StatusCog")
        if status_cog and self.config is not None and self.config.get("status_message_enabled", False):
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
                # Idempotente: view persistente (cores_dropdown) registrada no
                # cog_load mantém o dropdown vivo após restart — sem reenviar.
                await cores_cog.cores(canal_cores)

        pix_cog = self.get_cog("PixCog")
        if pix_cog:
            canal_pix = self._cfg_channel("pix_channel_id")
            if canal_pix:
                # Idempotente: só posta se a embed persistente ainda não existir.
                # A view foi re-registrada no cog_load do PixCog (custom_id fixo),
                # então o dropdown da mensagem já postada segue funcionando após
                # restart — sem apagar e reenviar a cada boot.
                await pix_cog.setup_planos_embed(canal_pix)

        ticket_cog = self.get_cog("TicketCog")
        if ticket_cog:
            canal_ticket = self._cfg_channel("tickets_channel_id")
            if canal_ticket:
                # Idempotente: views persistentes (abrir_suporte/doacao + fechar)
                # registradas no cog_load mantêm o painel e os botões dos tickets
                # abertos funcionando após restart — sem reenviar.
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


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, (commands.MissingPermissions, commands.MissingRole, commands.MissingAnyRole)):
        try:
            await ctx.send("❌ Você não tem permissão para usar este comando.")
        except Exception:
            pass
        return
    if isinstance(error, commands.CheckFailure):
        try:
            await ctx.send("❌ Você não pode usar este comando aqui.")
        except Exception:
            pass
        return
    if isinstance(error, commands.UserInputError):
        try:
            await ctx.send(f"❌ Uso inválido: {error}")
        except Exception:
            pass
        return
    traceback.print_exception(type(error), error, error.__traceback__)
    try:
        await ctx.send("❌ Ocorreu um erro inesperado. Tente novamente mais tarde.")
    except Exception:
        pass


load_dotenv()
TOKEN = os.getenv("TOKEN")


async def main():
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
