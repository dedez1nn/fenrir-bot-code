"""Cog Fenrir — define o canal onde os comandos do bot são permitidos."""

import logging

import discord
from discord.ext import commands

from services import gate
from repositories.server_channels import (
    get_all_command_channels,
    remove_command_channel,
    set_command_channel,
)

logger = logging.getLogger(__name__)


class FenrirCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        if self.bot.db is None:
            logger.warning("bot.db indisponível — gate de canal não carregado.")
            return
        channels = await get_all_command_channels(self.bot.db)
        gate.load(channels)
        logger.info("Gate de canal carregado: %d guild(s) configurada(s)", len(channels))

    @commands.command(name="canal-fenrir")
    @commands.has_permissions(administrator=True)
    async def cmd_canal_fenrir(
        self, ctx: commands.Context, canal: discord.TextChannel | None = None
    ) -> None:
        if self.bot.db is None:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        guild_id = ctx.guild.id

        if canal:
            await set_command_channel(self.bot.db, guild_id, canal.id)
            gate.set_channel(guild_id, canal.id)
            embed = discord.Embed(
                title="✅ Canal de comandos configurado",
                description=f"Comandos do bot restritos a {canal.mention}.\nComandos de administração continuam funcionando em qualquer canal.",
                color=0x3B82F6,
            )
        else:
            await remove_command_channel(self.bot.db, guild_id)
            gate.remove_channel(guild_id)
            embed = discord.Embed(
                title="✅ Restrição removida",
                description="Comandos do bot liberados em todos os canais.",
                color=0x3B82F6,
            )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FenrirCog(bot))
