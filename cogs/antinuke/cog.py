from __future__ import annotations

from typing import Literal

import discord
from discord.ext import commands

from .config import AntinukeConfig
from .monitor import SlidingWindow, ServerSeverity
from .lockdown import LockdownManager


class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = AntinukeConfig()
        self.window = SlidingWindow()
        self.severity = ServerSeverity()
        self.lockdown = LockdownManager()

    async def cog_load(self) -> None:
        pool = getattr(self.bot, "db", None)
        if pool is None:
            return
        try:
            self.config = await AntinukeConfig.load_from_db(pool, self._primary_guild_id())
        except Exception:
            self.config = AntinukeConfig()

    async def reload_config_from_db(self) -> None:
        """Recarrega AntinukeConfig do banco. Chamado pelo bot após NOTIFY da API."""
        pool = getattr(self.bot, "db", None)
        if pool is None:
            return
        try:
            self.config = await AntinukeConfig.load_from_db(pool, self._primary_guild_id())
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("reload_config_from_db antinuke falhou: %s", exc)

    def _primary_guild_id(self) -> int:
        cfg = getattr(self.bot, "config", None)
        if cfg is not None:
            try:
                return int(cfg.guild_id)
            except (AttributeError, TypeError, ValueError):
                pass
        guilds = self.bot.guilds
        return guilds[0].id if guilds else 0

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _is_whitelisted(self, user_id: int) -> bool:
        return user_id in self.config.whitelist_ids

    async def _alert(
        self,
        guild: discord.Guild,
        event: str,
        detail: str,
        executor: discord.Member | discord.User | None = None,
    ) -> None:
        if not self.config.enabled:
            return
        sev = self.severity.increment(guild.id)
        stage = self.config.severity_thresholds.get(min(sev, max(self.config.severity_thresholds)))

        log_ch = self._log_channel(guild)
        if log_ch:
            color = {
                "log": discord.Color.gold(),
                "ping": discord.Color.orange(),
                "slowmode": discord.Color.dark_orange(),
                "lockdown": discord.Color.dark_red(),
            }.get(stage, discord.Color.gold())

            embed = discord.Embed(
                title=f"⚠️ AntiNuke — {event}",
                description=detail,
                color=color,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Severidade", value=f"`{sev}` → estágio `{stage}`", inline=True)
            if executor:
                embed.add_field(name="Executor", value=f"{executor.mention} (`{executor.id}`)", inline=True)
            embed.add_field(name="Modo", value="`alert-only`" if self.config.alert_only else "`ativo`", inline=True)

            ping = ""
            if stage in ("ping", "slowmode", "lockdown") and self.config.admin_ping_ids:
                ping = " ".join(f"<@{uid}>" for uid in self.config.admin_ping_ids)

            try:
                await log_ch.send(content=ping or None, embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

        if self.config.alert_only:
            return

        if stage == "slowmode":
            count = await self.lockdown.apply_slowmode(guild, seconds=30, reason=event)
            if log_ch:
                try:
                    await log_ch.send(f"🐌 Slowmode de 30s aplicado em {count} canais.")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        elif stage == "lockdown" and not self.lockdown.is_locked(guild.id):
            await self.lockdown.lockdown(
                guild,
                reason=f"{event}: {detail}",
                duration_minutes=self.config.lockdown_duration_minutes,
                log_channel_id=self.config.log_channel_id,
            )

    def _log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if not self.config.log_channel_id:
            return None
        return guild.get_channel(self.config.log_channel_id)

    # ------------------------------------------------------------------ #
    # Listeners
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild = member.guild
        count, window = self.config.join_rate
        total = self.window.record_and_count(f"{guild.id}:joins", window)

        age_days = (discord.utils.utcnow() - member.created_at).days
        new_account = age_days < self.config.min_account_age_days

        if new_account:
            await self._alert(
                guild,
                "Conta nova",
                f"{member.mention} criada há **{age_days}d** (mínimo: {self.config.min_account_age_days}d)",
                executor=member,
            )

        if total >= count:
            await self._alert(
                guild,
                "Raid detectado",
                f"**{total}** joins nos últimos **{window:g}s** (limite: {count})",
            )
            self.window.clear(f"{guild.id}:joins")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            executor = entry.user
            break
        else:
            executor = None

        if executor and self._is_whitelisted(executor.id):
            return

        count, window = self.config.channel_delete_rate
        key = f"{guild.id}:{getattr(executor, 'id', 0)}:ch_del"
        total = self.window.record_and_count(key, window)

        if total >= count:
            await self._alert(
                guild,
                "Deleção em massa de canais",
                f"**{total}** canais deletados em **{window:g}s** (limite: {count})",
                executor=executor,
            )
            self.window.clear(key)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        guild = role.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            executor = entry.user
            break
        else:
            executor = None

        if executor and self._is_whitelisted(executor.id):
            return

        count, window = self.config.role_delete_rate
        key = f"{guild.id}:{getattr(executor, 'id', 0)}:role_del"
        total = self.window.record_and_count(key, window)

        if total >= count:
            await self._alert(
                guild,
                "Deleção em massa de cargos",
                f"**{total}** cargos deletados em **{window:g}s** (limite: {count})",
                executor=executor,
            )
            self.window.clear(key)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            executor = entry.user
            break
        else:
            executor = None

        if executor and self._is_whitelisted(executor.id):
            return

        count, window = self.config.ban_rate
        key = f"{guild.id}:{getattr(executor, 'id', 0)}:bans"
        total = self.window.record_and_count(key, window)

        if total >= count:
            await self._alert(
                guild,
                "Mass ban detectado",
                f"**{total}** bans em **{window:g}s** (limite: {count})",
                executor=executor,
            )
            self.window.clear(key)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guild = member.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                executor = entry.user
                break
        else:
            return  # saída voluntária, não kick

        if self._is_whitelisted(executor.id):
            return

        count, window = self.config.kick_rate
        key = f"{guild.id}:{executor.id}:kicks"
        total = self.window.record_and_count(key, window)

        if total >= count:
            await self._alert(
                guild,
                "Mass kick detectado",
                f"**{total}** kicks em **{window:g}s** (limite: {count})",
                executor=executor,
            )
            self.window.clear(key)

    # ------------------------------------------------------------------ #
    # Slash commands
    # ------------------------------------------------------------------ #

    @commands.command(name="antinuke_status")
    @commands.has_permissions(administrator=True)
    async def cmd_status(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        sev = self.severity.current(guild.id)
        locked = self.lockdown.is_locked(guild.id)

        embed = discord.Embed(title="🛡️ AntiNuke — status", color=discord.Color.blurple())
        embed.add_field(name="Modo", value="`alert-only`" if self.config.alert_only else "`ativo`", inline=True)
        embed.add_field(name="Severidade atual", value=f"`{sev}`", inline=True)
        embed.add_field(name="Lockdown", value="🔒 Ativo" if locked else "🔓 Inativo", inline=True)

        thresholds = (
            f"Joins: `{self.config.join_rate[0]}`/{self.config.join_rate[1]:g}s\n"
            f"Canais deletados: `{self.config.channel_delete_rate[0]}`/{self.config.channel_delete_rate[1]:g}s\n"
            f"Roles deletadas: `{self.config.role_delete_rate[0]}`/{self.config.role_delete_rate[1]:g}s\n"
            f"Bans: `{self.config.ban_rate[0]}`/{self.config.ban_rate[1]:g}s\n"
            f"Kicks: `{self.config.kick_rate[0]}`/{self.config.kick_rate[1]:g}s"
        )
        embed.add_field(name="Thresholds", value=thresholds, inline=False)
        embed.add_field(
            name="Conta mínima",
            value=f"`{self.config.min_account_age_days}` dias",
            inline=True,
        )
        embed.add_field(
            name="Lockdown duração",
            value=f"`{self.config.lockdown_duration_minutes}` min",
            inline=True,
        )
        embed.add_field(
            name="Whitelist",
            value=f"`{len(self.config.whitelist_ids)}` usuários",
            inline=True,
        )
        await ctx.send(embed=embed)

    @commands.command(name="antinuke_modo")
    @commands.has_permissions(administrator=True)
    async def cmd_modo(self, ctx: commands.Context, modo: Literal["alert", "active"]) -> None:
        self.config.alert_only = modo == "alert"
        label = "alert-only" if self.config.alert_only else "ativo"
        await ctx.send(f"✅ Modo definido para `{label}`.")

    @commands.command(name="antinuke_whitelist")
    @commands.has_permissions(administrator=True)
    async def cmd_whitelist(
        self,
        ctx: commands.Context,
        user: discord.Member,
        action: Literal["add", "remove"],
    ) -> None:
        if action == "add":
            if user.id not in self.config.whitelist_ids:
                self.config.whitelist_ids.append(user.id)
            msg = f"✅ {user.mention} adicionado à whitelist do antinuke."
        else:
            self.config.whitelist_ids = [i for i in self.config.whitelist_ids if i != user.id]
            msg = f"✅ {user.mention} removido da whitelist do antinuke."
        await ctx.send(msg)

    @commands.command(name="antinuke_ping_admin")
    @commands.has_permissions(administrator=True)
    async def cmd_ping_admin(
        self,
        ctx: commands.Context,
        user: discord.Member,
        action: Literal["add", "remove"],
    ) -> None:
        if action == "add":
            if user.id not in self.config.admin_ping_ids:
                self.config.admin_ping_ids.append(user.id)
            msg = f"✅ {user.mention} será pingado em alertas de severidade 2+."
        else:
            self.config.admin_ping_ids = [i for i in self.config.admin_ping_ids if i != user.id]
            msg = f"✅ {user.mention} removido dos pings de alerta."
        await ctx.send(msg)

    @commands.command(name="antinuke_canal_log")
    @commands.has_permissions(administrator=True)
    async def cmd_canal_log(self, ctx: commands.Context, canal: discord.TextChannel) -> None:
        self.config.log_channel_id = canal.id
        await ctx.send(f"✅ Canal de log definido: {canal.mention}")

    @commands.command(name="antinuke_lockdown")
    @commands.has_permissions(administrator=True)
    async def cmd_lockdown(self, ctx: commands.Context, *, motivo: str = "Manual") -> None:
        ok = await self.lockdown.lockdown(
            ctx.guild,
            reason=motivo,
            duration_minutes=self.config.lockdown_duration_minutes,
            log_channel_id=self.config.log_channel_id,
        )
        if ok:
            await ctx.send(f"🔒 Lockdown ativado por **{self.config.lockdown_duration_minutes} min**.")
        else:
            await ctx.send("⚠️ Servidor já está em lockdown.")

    @commands.command(name="antinuke_unlock")
    @commands.has_permissions(administrator=True)
    async def cmd_unlock(self, ctx: commands.Context) -> None:
        ok = await self.lockdown.unlock(
            ctx.guild,
            reason=f"Unlock manual por {ctx.author}",
            log_channel_id=self.config.log_channel_id,
        )
        if ok:
            await ctx.send("🔓 Lockdown removido.")
        else:
            await ctx.send("ℹ️ Servidor não estava em lockdown.")

    @commands.command(name="antinuke_reset_severidade")
    @commands.has_permissions(administrator=True)
    async def cmd_reset_sev(self, ctx: commands.Context) -> None:
        self.severity.reset(ctx.guild.id)
        await ctx.send("✅ Severidade zerada.")

    @commands.command(name="antinuke_toggle")
    @commands.has_permissions(administrator=True)
    async def cmd_toggle(self, ctx: commands.Context, estado: Literal["on", "off"]) -> None:
        self.config.enabled = estado == "on"
        label = "✅ ativado" if self.config.enabled else "⛔ desativado"
        await ctx.send(f"🛡️ Anti-Nuke {label}.")
