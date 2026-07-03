"""Comandos !config_status e !config-atual — diagnóstico de configuração para admins.

Mostram estado de validação de todas as features sem acessar o DB diretamente:
usam validate_all() contra o bot.config em memória. !config-atual complementa
com módulos que não passam por validate_all (copa/selfbot/canal-fenrir/status,
antispam/antinuke) e paginação.
"""

import discord
from discord.ext import commands

# feature (chave de VALIDATORS em db/validators.py) -> comando ! para corrigir.
# Quando não existe comando dedicado hoje, diz isso explicitamente em vez de
# inventar um nome errado.
_FEATURE_COMMANDS: dict[str, str] = {
    "tickets": "⚠️ Sem comando ! hoje — só via painel administrativo (API)",
    "voice_creator": "!config-canais-sistemas",
    "member_logs": "!config-canais-embeds",
    "colors": "!config-cargos",
    "premium": "Defina ACCESS_TOKEN no `.env` (Mercado Pago) — não é um comando !",
    "xp": "⚠️ Sem comando ! hoje — levelup_role_map só via painel administrativo (API)",
    "adventures": "!config-canais-sistemas",
    "guild_raids": "!config-canais-sistemas",
    "antispam": "!antispam_toggle / !antispam_canal_log / !antispam_threshold",
    "antinuke": "!antinuke_toggle / !antinuke_canal_log",
    "economy": "!config-economia",
    "guilds": "Sem pré-requisito de configuração",
    "riot": "Defina RIOT_API_KEY no `.env`",
    "steam": "Defina STEAM_API_KEY no `.env`",
    "gnews": "Defina GNEWS_API_KEY no `.env`",
    "invite_blocker": "Sem pré-requisito além da permissão Manage Messages do bot",
    "auto_remove_bots": "Sem pré-requisito além da permissão Kick Members do bot",
    "status": "!config-canais-log",
}

_ENTRIES_PER_PAGE = 6


class ConfigAtualView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.page = 0
        self._update_buttons()

    def _update_buttons(self):
        self.btn_prev.disabled = self.page == 0
        self.btn_counter.label = f"{self.page + 1} / {len(self.pages)}"
        self.btn_next.disabled = self.page >= len(self.pages) - 1

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.primary, disabled=True)
    async def btn_counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(self.pages) - 1:
            self.page += 1
            self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class ConfigCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="config_status")
    @commands.has_permissions(administrator=True)
    async def config_status(self, ctx: commands.Context):
        cfg = getattr(self.bot, "config", None)
        if cfg is None:
            await ctx.send("❌ server_config não carregada (bot em modo degradado).")
            return

        try:
            from db.validators import validate_all
            all_errors = validate_all(cfg.to_dict())
        except Exception as exc:
            await ctx.send(f"❌ Erro ao rodar validação: {exc}")
            return

        ok_features = [f for f, errs in all_errors.items() if not errs]
        bad_features = {f: errs for f, errs in all_errors.items() if errs}

        embed = discord.Embed(
            title="🔍 Diagnóstico de Configuração",
            color=discord.Color.green() if not bad_features else discord.Color.orange(),
        )

        if ok_features:
            embed.add_field(
                name=f"✅ Features OK ({len(ok_features)})",
                value=", ".join(f"`{f}`" for f in sorted(ok_features)),
                inline=False,
            )

        for feature, errors in sorted(bad_features.items()):
            lines = []
            for err in errors:
                lines.append(f"**{err.get('code')}** — `{err.get('field')}`\n{err.get('message')}\n> {err.get('suggestion', '')}")
            embed.add_field(
                name=f"⚠️ {feature}",
                value="\n\n".join(lines)[:1024],
                inline=False,
            )

        if not bad_features:
            embed.description = "Todas as features estão corretamente configuradas."
        else:
            embed.description = f"{len(bad_features)} feature(s) com configuração incompleta."

        await ctx.send(embed=embed)

    @commands.command(name="config-atual")
    @commands.has_permissions(administrator=True)
    async def config_atual(self, ctx: commands.Context):
        """Lista todos os módulos configuráveis: o que está OK, o que falta e o comando pra corrigir."""
        cfg = getattr(self.bot, "config", None)
        if cfg is None:
            await ctx.send("❌ server_config não carregada (bot em modo degradado).")
            return

        try:
            from db.validators import validate_all
            all_errors = validate_all(cfg.to_dict())
        except Exception as exc:
            await ctx.send(f"❌ Erro ao rodar validação: {exc}")
            return

        entries: list[tuple[str, bool | None, str, str]] = []

        for feature, errors in sorted(all_errors.items()):
            ok = not errors
            if ok:
                detalhe = "Configurado corretamente."
            else:
                detalhe = " / ".join(e.get("message", "") for e in errors)
            entries.append((feature, ok, detalhe, _FEATURE_COMMANDS.get(feature, "—")))

        # Módulos migrados do Mongo / fora do validate_all — checados direto em server_config.
        cfg_dict = cfg.to_dict()
        entries.append((
            "canal-fenrir",
            bool(cfg_dict.get("fenrir_command_channel_id")),
            "Restringe comandos a um canal." if cfg_dict.get("fenrir_command_channel_id")
            else "Sem restrição de canal configurada (comandos liberados em qualquer canal).",
            "!canal-fenrir",
        ))
        entries.append((
            "copa-2026",
            bool(cfg_dict.get("copa_notify_channel_id")),
            "Canal de notificações da Copa configurado." if cfg_dict.get("copa_notify_channel_id")
            else "Canal de notificações da Copa não configurado.",
            "!config-copa",
        ))
        entries.append((
            "selfbot-trap",
            bool(cfg_dict.get("selfbot_trap_channel_id")),
            "Armadilha de selfbot ativa." if cfg_dict.get("selfbot_trap_channel_id")
            else "Armadilha de selfbot não configurada.",
            "!config-selfbot",
        ))
        entries.append((
            "selfbot-log",
            bool(cfg_dict.get("selfbot_log_channel_id")),
            "Canal de log dedicado configurado." if cfg_dict.get("selfbot_log_channel_id")
            else "Sem canal de log dedicado (usa o canal do sistema como fallback).",
            "!config-selfbot",
        ))
        status_msg_on = bool(cfg_dict.get("status_message_enabled"))
        entries.append((
            "status-mensagem",
            None,
            "Ligada — embed de status é postado em on_ready." if status_msg_on
            else "Desligada (padrão) — embed de status não é postado em on_ready.",
            "!status-mensagem on|off",
        ))

        if self.bot.db is not None:
            try:
                async with self.bot.db.acquire() as conn:
                    antispam_row = await conn.fetchrow(
                        "SELECT 1 FROM antispam_config WHERE guild_id = $1", ctx.guild.id
                    )
                    antinuke_row = await conn.fetchrow(
                        "SELECT 1 FROM antinuke_config WHERE guild_id = $1", ctx.guild.id
                    )
                entries.append((
                    "antispam-config",
                    None,
                    "Config própria salva no banco." if antispam_row
                    else "Nunca configurado — rodando com os valores padrão do código.",
                    "!antispam_status",
                ))
                entries.append((
                    "antinuke-config",
                    None,
                    "Config própria salva no banco." if antinuke_row
                    else "Nunca configurado — rodando com os valores padrão do código.",
                    "!antinuke_status",
                ))
            except Exception:
                pass

        ok_count = sum(1 for _, ok, _, _ in entries if ok is True)
        bad_count = sum(1 for _, ok, _, _ in entries if ok is False)
        info_count = sum(1 for _, ok, _, _ in entries if ok is None)

        pages: list[discord.Embed] = []
        chunks = [entries[i:i + _ENTRIES_PER_PAGE] for i in range(0, len(entries), _ENTRIES_PER_PAGE)]
        total_pages = max(1, len(chunks))

        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="⚙️ Configuração Atual do Bot",
                description=f"✅ {ok_count} OK · ❌ {bad_count} faltando · ℹ️ {info_count} informativo(s)",
                color=discord.Color.orange() if bad_count else discord.Color.green(),
            )
            for feature, ok, detalhe, comando in chunk:
                icon = "✅" if ok is True else ("❌" if ok is False else "ℹ️")
                embed.add_field(
                    name=f"{icon} {feature}",
                    value=f"{detalhe}\n**Comando:** {comando}",
                    inline=False,
                )
            embed.set_footer(text=f"Página {i + 1} de {total_pages}")
            pages.append(embed)

        if len(pages) <= 1:
            await ctx.send(embed=pages[0])
            return

        view = ConfigAtualView(pages)
        await ctx.send(embed=pages[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCheck(bot))
