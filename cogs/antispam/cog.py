from __future__ import annotations

from pathlib import Path
from typing import Literal

import discord
from discord.ext import commands

from .config import AntispamConfig
from .storage import JSONStorage
from .pg_storage import PgStorage
from .scoring import ScoreManager
from .detector import Detector
from .punisher import Punisher
from .audit import AuditLogger


DATA_PATH = str(Path(__file__).parent.parent.parent / "data" / "antispam.json")


class AntiSpam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = AntispamConfig()
        # Storage e managers dependentes são instanciados em cog_load para que
        # bot.db já esteja resolvido (Postgres vs. JSON fallback).
        self.storage = None
        self.scoring = None
        self.detector = None
        self.punisher = None
        self.audit = None

    async def cog_load(self) -> None:
        pool = getattr(self.bot, "db", None)
        if pool is not None:
            self.storage = PgStorage(pool)
            try:
                self.config = await AntispamConfig.load_from_db(pool, self._primary_guild_id())
            except Exception:
                self.config = AntispamConfig()
        else:
            self.storage = JSONStorage(DATA_PATH)

        self.scoring = ScoreManager(self.storage, self.config)
        self.detector = Detector(self.config)
        self.punisher = Punisher(self.storage, self.scoring, self.config)
        self.audit = AuditLogger(self.bot, self.config)
        await self.storage.load()

    def _primary_guild_id(self) -> int:
        # Phase 1: somente uma guild ativa. Phase 6+ trocaria para multi-guild.
        cfg = getattr(self.bot, "config", None)
        if cfg is not None:
            try:
                return int(cfg.guild_id)
            except (AttributeError, TypeError, ValueError):
                pass
        guilds = self.bot.guilds
        return guilds[0].id if guilds else 0

    async def reload_config_from_db(self) -> None:
        """Recarrega AntispamConfig do banco. Chamado pelo bot após NOTIFY da API."""
        pool = getattr(self.bot, "db", None)
        if pool is None:
            return
        try:
            new_cfg = await AntispamConfig.load_from_db(pool, self._primary_guild_id())
            self.config = new_cfg
            # Propaga config atualizada para os managers que guardam referência
            if self.scoring:
                self.scoring.config = new_cfg
            if self.detector:
                self.detector.config = new_cfg
            if self.punisher:
                self.punisher.config = new_cfg
            if self.audit:
                self.audit.config = new_cfg
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("reload_config_from_db antispam falhou: %s", exc)

    async def _is_exempt(self, message: discord.Message) -> bool:
        if message.author.bot or message.guild is None:
            return True
        author = message.author
        if isinstance(author, discord.Member) and author.guild_permissions.manage_messages:
            return True
        guild_state = await self.storage.guild(message.guild.id)
        if str(author.id) in guild_state.get("whitelist", []):
            return True
        return False

    async def _process(self, message: discord.Message, edited: bool = False) -> None:
        if not self.config.enabled:
            return
        if await self._is_exempt(message):
            return

        user_state = await self.storage.user(message.guild.id, message.author.id)
        violations = self.detector.analyze(message, user_state, edited=edited)
        if not violations:
            await self.storage.save()
            return

        delta = Detector.total_score(violations)
        reason = ", ".join(v.kind for v in violations)
        evidence = {
            "channel_id": message.channel.id,
            "message_id": message.id,
            "snippet": (message.content or "")[:200],
        }
        score = await self.scoring.add(
            message.guild.id, message.author.id, delta, reason, evidence
        )

        if message.guild.me.guild_permissions.manage_messages:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass

        action_obj = None
        if isinstance(message.author, discord.Member):
            action_obj = await self.punisher.evaluate(message.author, score, reason)
            await self.punisher.sync_blacklist_role(message.author, score)

        await self.audit.log(
            message,
            violations,
            score,
            action_obj.name if action_obj else None,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._process(message, edited=False)

    @commands.Cog.listener()
    async def on_message_edit(self, _before: discord.Message, after: discord.Message) -> None:
        await self._process(after, edited=True)

    @commands.command(name="antispam_status")
    @commands.has_permissions(manage_guild=True)
    async def cmd_status(self, ctx: commands.Context):
        if ctx.guild is None:
            return
        g = await self.storage.guild(ctx.guild.id)
        users = g.get("users", {})
        active = sum(1 for u in users.values() if (u.get("score") or 0) > 0)
        embed = discord.Embed(title="🛡️ Anti-Spam — status", color=discord.Color.blurple())
        embed.add_field(name="Usuários monitorados", value=f"`{len(users)}`", inline=True)
        embed.add_field(name="Com score > 0", value=f"`{active}`", inline=True)
        embed.add_field(name="Whitelist", value=f"`{len(g.get('whitelist', []))}`", inline=True)
        ladder = "\n".join(f"`{s}` → **{a}**" for s, a in sorted(self.config.ladder.items()))
        embed.add_field(name="Ladder", value=ladder, inline=False)
        embed.add_field(name="Decay", value=f"`{self.config.decay_per_minute}` ponto/min", inline=True)
        embed.add_field(
            name="Blacklist",
            value=f"aplica em `{self.config.blacklist_apply_score}`, remove em `{self.config.blacklist_remove_score}`",
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="antispam_reset")
    @commands.has_permissions(manage_guild=True)
    async def cmd_reset(self, ctx: commands.Context, user: discord.Member):
        await self.scoring.reset(ctx.guild.id, user.id)
        await ctx.send(f"✅ Score de {user.mention} foi zerado.")

    @commands.command(name="antispam_whitelist")
    @commands.has_permissions(manage_guild=True)
    async def cmd_whitelist(
        self,
        ctx: commands.Context,
        user: discord.Member,
        action: Literal["add", "remove"],
    ):
        g = await self.storage.guild(ctx.guild.id)
        wl = g.setdefault("whitelist", [])
        uid = str(user.id)
        if action == "add":
            if uid not in wl:
                wl.append(uid)
            msg = f"✅ {user.mention} adicionado à whitelist."
        else:
            if uid in wl:
                wl.remove(uid)
            msg = f"✅ {user.mention} removido da whitelist."
        await self.storage.save()
        await ctx.send(msg)

    @commands.command(name="antispam_threshold")
    @commands.has_permissions(manage_guild=True)
    async def cmd_threshold(
        self,
        ctx: commands.Context,
        score: int,
        action: str,
    ):
        if not (1 <= score <= 200):
            await ctx.send("❌ Score deve estar entre 1 e 200.")
            return
        valid = {"warn", "timeout_5", "timeout_10", "kick", "ban", "none"}
        if action not in valid:
            await ctx.send(f"❌ Ação inválida. Use: {', '.join(sorted(valid))}")
            return
        if action == "none":
            self.config.ladder.pop(int(score), None)
        else:
            self.config.ladder[int(score)] = action
        pool = getattr(self.bot, "db", None)
        if pool is not None:
            await self.config.save_to_db(pool, self._primary_guild_id())
        await ctx.send(f"✅ Threshold `{score}` → `{action}`.")

    @commands.command(name="antispam_canal_log")
    @commands.has_permissions(manage_guild=True)
    async def cmd_canal_log(
        self,
        ctx: commands.Context,
        canal: discord.TextChannel | None = None,
    ):
        guild = ctx.guild

        try:
            if canal is not None:
                self.config.log_channel_id = canal.id
                pool = getattr(self.bot, "db", None)
                if pool is not None:
                    await self.config.save_to_db(pool, self._primary_guild_id())
                await ctx.send(f"✅ Canal de log definido: {canal.mention}")
                return

            if not guild.me.guild_permissions.manage_channels:
                await ctx.send(
                    "❌ Preciso da permissão **Gerenciar Canais** para criar o canal.\n"
                    "Crie um canal manualmente e use `!antispam_canal_log` selecionando-o."
                )
                return

            existing = discord.utils.get(guild.text_channels, name="antispam-logs")
            if existing is not None:
                self.config.log_channel_id = existing.id
                pool = getattr(self.bot, "db", None)
                if pool is not None:
                    await self.config.save_to_db(pool, self._primary_guild_id())
                await ctx.send(f"⚠️ Canal {existing.mention} já existe — definido como canal de log.")
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, embed_links=True
                ),
            }
            for role in guild.roles:
                if role.managed:
                    continue
                if role.permissions.administrator or role.permissions.manage_messages:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=False, read_message_history=True
                    )

            category = next(
                (
                    cat for cat in guild.categories
                    if any(kw in cat.name.lower() for kw in ("mod", "admin", "staff", "log", "segur"))
                ),
                None,
            )

            new_channel = await guild.create_text_channel(
                name="antispam-logs",
                overwrites=overwrites,
                category=category,
                topic="Logs automáticos do sistema Anti-Spam do Fenrir Security.",
                reason=f"Canal de log Anti-Spam criado por {ctx.author}",
            )

            self.config.log_channel_id = new_channel.id
            pool = getattr(self.bot, "db", None)
            if pool is not None:
                await self.config.save_to_db(pool, self._primary_guild_id())

            await new_channel.send(embed=discord.Embed(
                title="🛡️ Anti-Spam — Canal de Auditoria",
                description="Este canal registra automaticamente todas as detecções do sistema anti-spam.",
                color=discord.Color.blurple(),
            ))

            embed = discord.Embed(
                title="✅ Canal de log criado",
                description=f"Canal {new_channel.mention} configurado.",
                color=discord.Color.green(),
            )
            embed.add_field(name="Categoria", value=category.name if category else "Raiz do servidor", inline=True)
            embed.add_field(name="ID", value=f"`{new_channel.id}`", inline=True)
            embed.add_field(
                name="Visível para",
                value="Cargos com **Gerenciar Mensagens** ou **Administrador**",
                inline=False,
            )
            await ctx.send(embed=embed)

        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ Erro: `{e}`")

    @commands.command(name="infractions")
    @commands.has_permissions(manage_messages=True)
    async def cmd_infractions(self, ctx: commands.Context, user: discord.Member):
        score = await self.scoring.current_score(ctx.guild.id, user.id)
        state = await self.storage.user(ctx.guild.id, user.id)
        infractions = state.get("infractions", [])[-10:]
        embed = discord.Embed(
            title=f"📋 Infrações — {user}",
            color=discord.Color.red() if score >= 10 else discord.Color.gold(),
        )
        embed.add_field(name="Score atual", value=f"`{score:.1f}`", inline=True)
        embed.add_field(name="Total registradas", value=f"`{len(state.get('infractions', []))}`", inline=True)
        embed.add_field(name="Blacklisted", value="✅" if state.get("blacklisted") else "—", inline=True)
        if infractions:
            lines = [
                f"<t:{int(i.get('ts', 0))}:R> · `+{i.get('delta', 0)}` · {i.get('reason', '')}"
                for i in infractions
            ]
            embed.add_field(name="Últimas 10", value="\n".join(lines)[:1024], inline=False)
        punishments = state.get("punishments", [])[-5:]
        if punishments:
            lines = [
                f"<t:{int(p.get('ts', 0))}:R> · `{p.get('action')}` · {p.get('reason', '')[:60]}"
                for p in punishments
            ]
            embed.add_field(name="Últimas punições", value="\n".join(lines)[:1024], inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="blacklist_add")
    @commands.has_permissions(manage_roles=True)
    async def cmd_bl_add(self, ctx: commands.Context, user: discord.Member, *, motivo: str = "Manual"):
        role = discord.utils.get(ctx.guild.roles, name=self.config.blacklist_role_name)
        if role is None:
            await ctx.send(f"❌ Cargo `{self.config.blacklist_role_name}` não existe neste servidor.")
            return
        try:
            await user.add_roles(role, reason=f"Blacklist manual: {motivo}")
        except discord.Forbidden:
            await ctx.send("❌ Sem permissão para gerenciar este cargo.")
            return
        state = await self.storage.user(ctx.guild.id, user.id)
        state["blacklisted"] = True
        await self.storage.save()
        await ctx.send(f"✅ {user.mention} adicionado à blacklist.")

    @commands.command(name="blacklist_remove")
    @commands.has_permissions(manage_roles=True)
    async def cmd_bl_remove(self, ctx: commands.Context, user: discord.Member):
        role = discord.utils.get(ctx.guild.roles, name=self.config.blacklist_role_name)
        if role and role in user.roles:
            try:
                await user.remove_roles(role, reason="Blacklist removida manualmente")
            except discord.Forbidden:
                await ctx.send("❌ Sem permissão.")
                return
        state = await self.storage.user(ctx.guild.id, user.id)
        state["blacklisted"] = False
        await self.storage.save()
        await ctx.send(f"✅ {user.mention} removido da blacklist.")

    @commands.command(name="antispam_toggle")
    @commands.has_permissions(manage_guild=True)
    async def cmd_toggle(self, ctx: commands.Context, estado: Literal["on", "off"]) -> None:
        self.config.enabled = estado == "on"
        pool = getattr(self.bot, "db", None)
        if pool is not None:
            await self.config.save_to_db(pool, self._primary_guild_id())
        label = "✅ ativado" if self.config.enabled else "⛔ desativado"
        await ctx.send(f"🛡️ Anti-Spam {label}.")

    @commands.command(name="emergencia")
    @commands.has_permissions(administrator=True)
    async def cmd_emergencia(self, ctx: commands.Context) -> None:
        self.config.enabled = False

        antinuke = self.bot.get_cog("AntiNuke")
        if antinuke:
            antinuke.config.enabled = False

        embed = discord.Embed(
            title="🚨 EMERGÊNCIA — Sistemas desativados",
            description=(
                "**Anti-Spam** e **Anti-Nuke** foram desativados imediatamente.\n\n"
                "Use `!antispam_toggle on` e `!antinuke_toggle on` para reativar cada um."
            ),
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Executado por", value=ctx.author.mention, inline=True)
        embed.set_footer(text="Nenhuma moderação automática está ativa no momento.")
        await ctx.send(embed=embed)