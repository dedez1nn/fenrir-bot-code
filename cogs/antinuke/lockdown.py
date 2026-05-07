from __future__ import annotations

import asyncio
from datetime import timedelta

import discord


class LockdownManager:
    def __init__(self):
        self._locked: dict[int, bool] = {}
        self._unlock_tasks: dict[int, asyncio.Task] = {}

    def is_locked(self, guild_id: int) -> bool:
        return self._locked.get(guild_id, False)

    async def lockdown(
        self,
        guild: discord.Guild,
        reason: str,
        duration_minutes: int,
        log_channel_id: int | None = None,
    ) -> bool:
        if self._locked.get(guild.id):
            return False

        self._locked[guild.id] = True
        success_count = 0

        try:
            await guild.edit(
                verification_level=discord.VerificationLevel.highest,
                reason=f"AntiNuke lockdown: {reason}",
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is False:
                continue
            overwrite.send_messages = False
            try:
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=f"AntiNuke lockdown: {reason}",
                )
                success_count += 1
            except (discord.Forbidden, discord.HTTPException):
                pass

        if log_channel_id:
            ch = guild.get_channel(log_channel_id)
            if ch:
                embed = discord.Embed(
                    title="🔒 Servidor em LOCKDOWN",
                    description=f"**Motivo:** {reason}\n**Duração:** {duration_minutes} min\n**Canais bloqueados:** {success_count}",
                    color=discord.Color.dark_red(),
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await ch.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        task = asyncio.get_event_loop().create_task(
            self._auto_unlock(guild, duration_minutes, reason, log_channel_id)
        )
        self._unlock_tasks[guild.id] = task
        return True

    async def unlock(
        self,
        guild: discord.Guild,
        reason: str = "Manual",
        log_channel_id: int | None = None,
    ) -> bool:
        if not self._locked.get(guild.id):
            return False

        task = self._unlock_tasks.pop(guild.id, None)
        if task:
            task.cancel()

        self._locked[guild.id] = False

        try:
            await guild.edit(
                verification_level=discord.VerificationLevel.medium,
                reason=f"AntiNuke unlock: {reason}",
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is not False:
                continue
            overwrite.send_messages = None
            try:
                if overwrite.is_empty():
                    await channel.set_permissions(guild.default_role, overwrite=None, reason="AntiNuke unlock")
                else:
                    await channel.set_permissions(guild.default_role, overwrite=overwrite, reason="AntiNuke unlock")
            except (discord.Forbidden, discord.HTTPException):
                pass

        if log_channel_id:
            ch = guild.get_channel(log_channel_id)
            if ch:
                embed = discord.Embed(
                    title="🔓 Lockdown encerrado",
                    description=f"**Motivo:** {reason}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await ch.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        return True

    async def apply_slowmode(
        self,
        guild: discord.Guild,
        seconds: int = 30,
        reason: str = "",
    ) -> int:
        count = 0
        for channel in guild.text_channels:
            if channel.slowmode_delay >= seconds:
                continue
            try:
                await channel.edit(
                    slowmode_delay=seconds,
                    reason=f"AntiNuke slowmode: {reason}",
                )
                count += 1
            except (discord.Forbidden, discord.HTTPException):
                pass
        return count

    async def _auto_unlock(
        self,
        guild: discord.Guild,
        minutes: int,
        reason: str,
        log_channel_id: int | None,
    ) -> None:
        await asyncio.sleep(minutes * 60)
        await self.unlock(guild, reason=f"Auto-unlock após {minutes} min", log_channel_id=log_channel_id)
