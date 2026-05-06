from __future__ import annotations

from typing import Iterable

import discord

from .config import AntispamConfig
from .detector import Violation


class AuditLogger:
    def __init__(self, bot, config: AntispamConfig):
        self.bot = bot
        self.config = config

    async def log(
        self,
        message: discord.Message,
        violations: Iterable[Violation],
        score: float,
        action: str | None,
    ) -> None:
        cid = self.config.log_channel_id
        if not cid:
            return
        channel = self.bot.get_channel(cid)
        if channel is None:
            return

        violations = list(violations)
        if not violations:
            return

        embed = discord.Embed(
            title="🛡️ Anti-Spam — evento detectado",
            color=discord.Color.dark_orange() if action else discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Usuário", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Canal", value=message.channel.mention if hasattr(message.channel, "mention") else str(message.channel), inline=True)
        embed.add_field(name="Score atual", value=f"`{score:.1f}`", inline=True)
        embed.add_field(
            name="Violações",
            value="\n".join(f"• `{v.kind}` (+{v.score}) {v.detail}".rstrip() for v in violations)[:1024],
            inline=False,
        )
        if action:
            embed.add_field(name="Ação aplicada", value=f"`{action}`", inline=False)
        snippet = (message.content or "")[:500]
        if snippet:
            embed.add_field(name="Mensagem", value=f"```{snippet}```", inline=False)
        embed.set_footer(text=f"guild_id={message.guild.id}")

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass
