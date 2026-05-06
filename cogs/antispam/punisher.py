from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import discord

from .config import AntispamConfig
from .scoring import ScoreManager
from .storage import JSONStorage


@dataclass
class Action:
    name: str
    reason: str
    score: float


class Punisher:
    def __init__(
        self,
        storage: JSONStorage,
        scoring: ScoreManager,
        config: AntispamConfig,
    ):
        self.storage = storage
        self.scoring = scoring
        self.config = config

    async def evaluate(
        self,
        member: discord.Member,
        score: float,
        reason: str,
    ) -> Action | None:
        applied = self.config.threshold_for(int(score))
        if not applied:
            return None
        action = Action(name=applied, reason=reason, score=score)
        await self._enforce(member, action)
        await self.scoring.record_punishment(
            member.guild.id, member.id, action.name, reason
        )
        return action

    async def _enforce(self, member: discord.Member, action: Action) -> None:
        guild = member.guild
        try:
            if action.name == "warn":
                await self._dm(member, action)
            elif action.name == "timeout_5":
                await self._timeout(member, minutes=5, action=action)
            elif action.name == "timeout_10":
                await self._timeout(member, minutes=10, action=action)
            elif action.name == "kick":
                await self._dm(member, action)
                if guild.me.guild_permissions.kick_members:
                    await member.kick(reason=f"AntiSpam: {action.reason}")
            elif action.name == "ban":
                await self._dm(member, action)
                if guild.me.guild_permissions.ban_members:
                    await guild.ban(member, reason=f"AntiSpam: {action.reason}", delete_message_days=1)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _timeout(self, member: discord.Member, minutes: int, action: Action) -> None:
        if not member.guild.me.guild_permissions.moderate_members:
            return
        await member.timeout(
            timedelta(minutes=minutes),
            reason=f"AntiSpam: {action.reason}",
        )
        await self._dm(member, action, extra=f"Duração: {minutes} min.")

    async def _dm(self, member: discord.Member, action: Action, extra: str = "") -> None:
        try:
            embed = discord.Embed(
                title="⚠️ Sistema Anti-Spam",
                description=f"Ação automática aplicada em **{member.guild.name}**.",
                color=discord.Color.orange(),
            )
            embed.add_field(name="Ação", value=f"`{action.name}`", inline=True)
            embed.add_field(name="Score", value=f"`{action.score:.1f}`", inline=True)
            embed.add_field(name="Motivo", value=action.reason or "—", inline=False)
            if extra:
                embed.add_field(name="Detalhe", value=extra, inline=False)
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def sync_blacklist_role(
        self,
        member: discord.Member,
        score: float,
    ) -> str | None:
        guild = member.guild
        role = discord.utils.get(guild.roles, name=self.config.blacklist_role_name)
        if role is None:
            return None
        if not guild.me.guild_permissions.manage_roles or guild.me.top_role <= role:
            return None
        user_state = await self.storage.user(guild.id, member.id)
        has_role = role in member.roles
        if score >= self.config.blacklist_apply_score and not has_role:
            try:
                await member.add_roles(role, reason=f"AntiSpam blacklist (score={score:.1f})")
                user_state["blacklisted"] = True
                await self.storage.save()
                return "added"
            except (discord.Forbidden, discord.HTTPException):
                return None
        if score <= self.config.blacklist_remove_score and has_role and user_state.get("blacklisted"):
            try:
                await member.remove_roles(role, reason="AntiSpam blacklist auto-removed")
                user_state["blacklisted"] = False
                await self.storage.save()
                return "removed"
            except (discord.Forbidden, discord.HTTPException):
                return None
        return None
