import discord
from discord.ext import commands
from discord import app_commands

import time
from collections import defaultdict, deque

from utils import extract_urls
from detector import analyze_url, CUSTOM_DOMAINS, save_domain
from logger import setup_logger

logger = setup_logger()


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.log_channels = {}

        # rate limit (slash commands)
        self.COMMAND_LIMIT = 5
        self.WINDOW_SECONDS = 10
        self.COOLDOWN_SECONDS = 30

        self.user_commands = defaultdict(lambda: deque())
        self.user_blocked_until = {}

        self.last_dm = {}

    # -------------------------
    # RATE LIMIT
    # -------------------------
    def is_rate_limited(self, user_id: int):
        now = time.time()

        if user_id in self.user_blocked_until:
            if now < self.user_blocked_until[user_id]:
                return True
            else:
                del self.user_blocked_until[user_id]

        history = self.user_commands[user_id]

        while history and now - history[0] > self.WINDOW_SECONDS:
            history.popleft()

        history.append(now)

        if len(history) > self.COMMAND_LIMIT:
            self.user_blocked_until[user_id] = now + self.COOLDOWN_SECONDS
            return True

        return False

    def can_send_dm(self, user_id: int):
        now = time.time()
        if user_id not in self.last_dm or now - self.last_dm[user_id] > 30:
            self.last_dm[user_id] = now
            return True
        return False

    async def send_log(self, guild: discord.Guild, title: str, description: str, color=0xff0000):
        if guild.id not in self.log_channels:
            return

        channel_id = self.log_channels[guild.id]
        channel = guild.get_channel(channel_id)

        if not channel:
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        try:
            await channel.send(embed=embed)
        except:
            pass

    @app_commands.command(name="canal-log", description="Definir canal de logs")
    @app_commands.describe(channel="Canal onde os logs serão enviados")
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):

        # ideal restringir
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "Você precisa ser administrador para usar este comando.",
                ephemeral=True
            )

        self.log_channels[interaction.guild.id] = channel.id

        await interaction.response.send_message(
            f"Canal de logs definido para {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(name="blockdomain", description="Bloquear domínio")
    @app_commands.checks.has_permissions(administrator=True)
    async def block_domain(self, interaction: discord.Interaction, domain: str):
        if self.is_rate_limited(interaction.user.id):
            return await interaction.response.send_message(
                "Você está enviando comandos rápido demais.",
                ephemeral=True
            )

        domain = domain.lower()

        if domain in CUSTOM_DOMAINS:
            return await interaction.response.send_message(
                "Domínio já está na lista.",
                ephemeral=True
            )

        CUSTOM_DOMAINS.add(domain)
        save_domain(domain)

        await self.send_log(
        interaction.guild,
            "Domínio adicionado à Blacklist",
            f"Usuário: {interaction.user.mention}\nDomínio: {domain}",
            color=0xffaa00
        )

        await interaction.response.send_message(
            f"Domínio adicionado: {domain}",
            ephemeral=True
        )

    @app_commands.command(name="unblockdomain", description="Remover domínio da lista")
    @app_commands.checks.has_permissions(administrator=True)
    async def unblock_domain(self, interaction: discord.Interaction, domain: str):
        if self.is_rate_limited(interaction.user.id):
            return await interaction.response.send_message(
                "Você está enviando comandos rápido demais.",
                ephemeral=True
            )

        domain = domain.lower()

        if domain not in CUSTOM_DOMAINS:
            return await interaction.response.send_message(
                "Domínio não encontrado.",
                ephemeral=True
            )

        CUSTOM_DOMAINS.remove(domain)

        with open("domains.txt", "w") as f:
            for d in CUSTOM_DOMAINS:
                f.write(d + "\n")

        await self.send_log(
            interaction.guild,
            "Domínio liberado para uso",
            f"Usuário: {interaction.user.mention}\nDomínio: {domain}",
            color=0x00ff00
        )

        await interaction.response.send_message(
            f"Removido: {domain}\n
            Usuário: {message.author.mention}",
            ephemeral=True
        )

    # -------------------------
    # EVENTO: DETECÇÃO
    # -------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        urls = extract_urls(message.content)

        if not urls:
            return

        for url in urls:
            try:
                result = analyze_url(url)

                await self.send_log(
                    message.guild,
                    "Link suspeito detectado",
                    f"Usuário: {message.author.mention}\nURL: {url}\nStatus: {result['status']}",
                    color=0xff0000
                )

                if result["status"] in ["phishing", "suspicious", "blocked"]:
                    await message.delete()

                    try:
                        if self.can_send_dm(message.author.id):
                            await message.author.send(
                                f"⚠️ Sua mensagem foi removida por conter link suspeito:\n{url}\nStatus: {result['status']}"
                            )
                    except:
                        await message.channel.send(
                            f"{message.author.mention}, sua mensagem foi removida por link suspeito."
                        )

                    logger.warning(f"[DELETE] {message.author} | {url} | {result}")

            except Exception as e:
                logger.error(f"Erro ao analisar URL {url}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))