from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
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

    antispam_group = app_commands.Group(
        name="antispam",
        description="Administração do sistema anti-spam",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @antispam_group.command(name="status", description="Mostra estatísticas e thresholds atuais")
    async def cmd_status(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        g = await self.storage.guild(interaction.guild.id)
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @antispam_group.command(name="reset", description="Zera o score e infrações de um usuário")
    @app_commands.describe(user="Usuário alvo")
    async def cmd_reset(self, interaction: discord.Interaction, user: discord.Member):
        await self.scoring.reset(interaction.guild.id, user.id)
        await interaction.response.send_message(
            f"✅ Score de {user.mention} foi zerado.", ephemeral=True
        )

    @antispam_group.command(name="whitelist", description="Adiciona ou remove usuário da whitelist")
    @app_commands.describe(user="Usuário", action="add ou remove")
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
    ])
    async def cmd_whitelist(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        action: app_commands.Choice[str],
    ):
        g = await self.storage.guild(interaction.guild.id)
        wl = g.setdefault("whitelist", [])
        uid = str(user.id)
        if action.value == "add":
            if uid not in wl:
                wl.append(uid)
            msg = f"✅ {user.mention} adicionado à whitelist."
        else:
            if uid in wl:
                wl.remove(uid)
            msg = f"✅ {user.mention} removido da whitelist."
        await self.storage.save()
        await interaction.response.send_message(msg, ephemeral=True)

    @antispam_group.command(name="threshold", description="Ajusta um threshold da escada (score → ação)")
    @app_commands.describe(score="Score gatilho", action="warn|timeout_5|timeout_10|kick|ban|none (remove)")
    async def cmd_threshold(
        self,
        interaction: discord.Interaction,
        score: app_commands.Range[int, 1, 200],
        action: str,
    ):
        valid = {"warn", "timeout_5", "timeout_10", "kick", "ban", "none"}
        if action not in valid:
            await interaction.response.send_message(
                f"❌ Ação inválida. Use: {', '.join(sorted(valid))}", ephemeral=True
            )
            return
        if action == "none":
            self.config.ladder.pop(int(score), None)
        else:
            self.config.ladder[int(score)] = action
        pool = getattr(self.bot, "db", None)
        if pool is not None:
            await self.config.save_to_db(pool, self._primary_guild_id())
        await interaction.response.send_message(
            f"✅ Threshold `{score}` → `{action}`.", ephemeral=True
        )

    @antispam_group.command(
        name="canal_log",
        description="Define ou cria o canal de auditoria do anti-spam",
    )
    @app_commands.describe(canal="Selecione um canal existente (deixe vazio para criar automaticamente)")
    async def cmd_canal_log(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        try:
            if canal is not None:
                self.config.log_channel_id = canal.id
                pool = getattr(self.bot, "db", None)
                if pool is not None:
                    await self.config.save_to_db(pool, self._primary_guild_id())
                await interaction.followup.send(
                    f"✅ Canal de log definido: {canal.mention}", ephemeral=True
                )
                return

            if not guild.me.guild_permissions.manage_channels:
                await interaction.followup.send(
                    "❌ Preciso da permissão **Gerenciar Canais** para criar o canal.\n"
                    "Crie um canal manualmente e use `/antispam canal_log` selecionando-o.",
                    ephemeral=True,
                )
                return

            existing = discord.utils.get(guild.text_channels, name="antispam-logs")
            if existing is not None:
                self.config.log_channel_id = existing.id
                pool = getattr(self.bot, "db", None)
                if pool is not None:
                    await self.config.save_to_db(pool, self._primary_guild_id())
                await interaction.followup.send(
                    f"⚠️ Canal {existing.mention} já existe — definido como canal de log.",
                    ephemeral=True,
                )
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
                reason=f"Canal de log Anti-Spam criado por {interaction.user}",
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
            await interaction.followup.send(embed=embed, ephemeral=True)

        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.followup.send(f"❌ Erro: `{e}`", ephemeral=True)

    @app_commands.command(name="infractions", description="Lista infrações registradas de um usuário")
    @app_commands.default_permissions(manage_messages=True)
    async def cmd_infractions(self, interaction: discord.Interaction, user: discord.Member):
        score = await self.scoring.current_score(interaction.guild.id, user.id)
        state = await self.storage.user(interaction.guild.id, user.id)
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    blacklist_group = app_commands.Group(
        name="blacklist",
        description="Gestão manual do cargo de blacklist",
        default_permissions=discord.Permissions(manage_roles=True),
    )

    @blacklist_group.command(name="add", description="Aplica o cargo de blacklist manualmente")
    async def cmd_bl_add(self, interaction: discord.Interaction, user: discord.Member, motivo: str = "Manual"):
        role = discord.utils.get(interaction.guild.roles, name=self.config.blacklist_role_name)
        if role is None:
            await interaction.response.send_message(
                f"❌ Cargo `{self.config.blacklist_role_name}` não existe neste servidor.",
                ephemeral=True,
            )
            return
        try:
            await user.add_roles(role, reason=f"Blacklist manual: {motivo}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para gerenciar este cargo.", ephemeral=True)
            return
        state = await self.storage.user(interaction.guild.id, user.id)
        state["blacklisted"] = True
        await self.storage.save()
        await interaction.response.send_message(f"✅ {user.mention} adicionado à blacklist.", ephemeral=True)

    @blacklist_group.command(name="remove", description="Remove o cargo de blacklist")
    async def cmd_bl_remove(self, interaction: discord.Interaction, user: discord.Member):
        role = discord.utils.get(interaction.guild.roles, name=self.config.blacklist_role_name)
        if role and role in user.roles:
            try:
                await user.remove_roles(role, reason="Blacklist removida manualmente")
            except discord.Forbidden:
                await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
                return
        state = await self.storage.user(interaction.guild.id, user.id)
        state["blacklisted"] = False
        await self.storage.save()
        await interaction.response.send_message(f"✅ {user.mention} removido da blacklist.", ephemeral=True)

    @antispam_group.command(name="toggle", description="Liga ou desliga o sistema anti-spam")
    @app_commands.describe(estado="on para ativar, off para desativar")
    @app_commands.choices(estado=[
        app_commands.Choice(name="on — ativar", value="on"),
        app_commands.Choice(name="off — desativar", value="off"),
    ])
    async def cmd_toggle(self, interaction: discord.Interaction, estado: app_commands.Choice[str]) -> None:
        self.config.enabled = estado.value == "on"
        pool = getattr(self.bot, "db", None)
        if pool is not None:
            await self.config.save_to_db(pool, self._primary_guild_id())
        label = "✅ ativado" if self.config.enabled else "⛔ desativado"
        await interaction.response.send_message(
            f"🛡️ Anti-Spam {label}.", ephemeral=True
        )

    @app_commands.command(name="emergencia", description="EMERGÊNCIA: desativa Anti-Spam e Anti-Nuke imediatamente")
    @app_commands.default_permissions(administrator=True)
    async def cmd_emergencia(self, interaction: discord.Interaction) -> None:
        self.config.enabled = False

        antinuke = self.bot.get_cog("AntiNuke")
        if antinuke:
            antinuke.config.enabled = False

        embed = discord.Embed(
            title="🚨 EMERGÊNCIA — Sistemas desativados",
            description=(
                "**Anti-Spam** e **Anti-Nuke** foram desativados imediatamente.\n\n"
                "Use `/antispam toggle on` e `/antinuke toggle on` para reativar cada um."
            ),
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Executado por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Nenhuma moderação automática está ativa no momento.")
        await interaction.response.send_message(embed=embed)
        embed.s