import discord
from discord.ext import commands
from typing import Literal
import logging

log = logging.getLogger(__name__)


class ConfigBotModal(discord.ui.Modal, title="⚙️ Configuração do Bot"):
    """Modal base para input de valores."""
    pass


class ConfigBotView(discord.ui.View):
    """View interativa para navegação entre configurações."""

    def __init__(self, bot, guild_id, config_data, step, total_steps):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.config_data = config_data
        self.step = step
        self.total_steps = total_steps

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.step > 1:
            await self.show_step(interaction, self.step - 1)
        else:
            await interaction.response.send_message("❌ Você já está no primeiro passo.", ephemeral=True)

    @discord.ui.button(label="Próximo ▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.step < self.total_steps:
            await self.show_step(interaction, self.step + 1)
        else:
            await interaction.response.send_message("❌ Você já está no último passo.", ephemeral=True)

    @discord.ui.button(label="💾 Salvar Configurações", style=discord.ButtonStyle.green)
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.save_config(interaction)

    async def show_step(self, interaction: discord.Interaction, step: int):
        """Exibe o passo específico."""
        self.step = step
        embed = await self.get_step_embed()
        view = ConfigBotView(self.bot, self.guild_id, self.config_data, step, self.total_steps)
        await interaction.response.edit_message(embed=embed, view=view)

    async def get_step_embed(self) -> discord.Embed:
        """Retorna o embed para o passo atual."""
        guild = self.bot.get_guild(self.guild_id)
        embed = discord.Embed(title=f"⚙️ Configuração do Bot - Passo {self.step}/{self.total_steps}",
                              color=discord.Color.blue(), description="Use os botões abaixo para navegar.")

        if self.step == 1:
            embed.add_field(
                name="📢 Canais de Log",
                value=f"Configure os canais para logs de eventos importantes.\n\n"
                      f"• **Commands**: {self._format_channel(self.config_data.get('commands_channel_id'))}\n"
                      f"• **Status**: {self._format_channel(self.config_data.get('status_channel_id'))}\n"
                      f"• **Help**: {self._format_channel(self.config_data.get('help_channel_id'))}\n"
                      f"• **Antispam Log**: {self._format_channel(self.config_data.get('antispam_log_channel_id'))}\n"
                      f"• **Antinuke Log**: {self._format_channel(self.config_data.get('antinuke_log_channel_id'))}\n\n"
                      f"Para editar, use: `!config-canais-log`",
                inline=False
            )

        elif self.step == 2:
            embed.add_field(
                name="💰 Canais de Economia",
                value=f"Configure os canais para eventos da economia.\n\n"
                      f"• **Pix**: {self._format_channel(self.config_data.get('pix_channel_id'))}\n"
                      f"• **Loja**: {self._format_channel(self.config_data.get('colors_channel_id'))}\n"
                      f"• **Coins Log**: {self._format_channel(self.config_data.get('coins_log_channel_id'))}\n"
                      f"• **XP Log**: {self._format_channel(self.config_data.get('xp_log_channel_id'))}\n"
                      f"• **Level Up**: {self._format_channel(self.config_data.get('levelup_channel_id'))}\n\n"
                      f"Para editar, use: `!config-canais-embeds` (pix/loja) ou `!config-canais-sistemas` (coins/xp/levelup)",
                inline=False
            )

        elif self.step == 3:
            embed.add_field(
                name="🎫 Canais Especiais",
                value=f"Configure canais para sistemas especiais.\n\n"
                      f"• **Tickets Support**: {self._format_channel(self.config_data.get('ticket_support_category_id'))}\n"
                      f"• **Tickets Donation**: {self._format_channel(self.config_data.get('ticket_donation_category_id'))}\n"
                      f"• **Voice Creator**: {self._format_channel(self.config_data.get('voice_creator_channel_id'))}\n"
                      f"• **Adventure Log**: {self._format_channel(self.config_data.get('adventure_log_channel_id'))}\n"
                      f"• **Guild Raid**: {self._format_channel(self.config_data.get('guild_raid_channel_id'))}\n\n"
                      f"Para editar, use: `!config-canais-sistemas`",
                inline=False
            )

        elif self.step == 4:
            premium_prices = self.config_data.get('premium_prices', {})
            embed.add_field(
                name="💎 Preços Premium",
                value=f"Preços dos planos premium em Pix.\n\n"
                      f"• **Aventureiro**: R$ {premium_prices.get('aventureiro', 0)}\n"
                      f"• **Lendário**: R$ {premium_prices.get('lendario', 0)}\n"
                      f"• **Mítico**: R$ {premium_prices.get('mitico', 0)}\n\n"
                      f"Para editar, use: `!config-premium`",
                inline=False
            )

        elif self.step == 5:
            premium_multipliers = self.config_data.get('premium_multipliers', {})
            embed.add_field(
                name="📈 Multiplicadores Premium",
                value=f"Multiplicadores de XP e coins por plano.\n\n"
                      f"• **Aventureiro**: {premium_multipliers.get('aventureiro', 1)}x\n"
                      f"• **Lendário**: {premium_multipliers.get('lendario', 1)}x\n"
                      f"• **Mítico**: {premium_multipliers.get('mitico', 1)}x\n\n"
                      f"Sem comando dedicado — edite via painel administrativo (API).",
                inline=False
            )

        elif self.step == 6:
            embed.add_field(
                name="💰 Ganhos Diários",
                value=f"Valores de coins para interações.\n\n"
                      f"• **Daily**: {self.config_data.get('daily_coins', 10000)} coins\n"
                      f"• **Bonus Daily**: {self.config_data.get('daily_streak_bonus', 10000)} coins\n"
                      f"• **Mensagem**: {self.config_data.get('coins_por_mensagem', 5000)} coins\n"
                      f"• **Voz**: {self.config_data.get('coins_por_voz', 15000)} coins\n"
                      f"• **Bonus Nível**: {self.config_data.get('bonus_coins_por_nivel', 50000)} coins\n\n"
                      f"Para editar, use: `!config-economia`",
                inline=False
            )

        elif self.step == 7:
            embed.add_field(
                name="⭐ Ganhos de XP",
                value=f"Valores de XP para interações.\n\n"
                      f"• **Mensagem**: {self.config_data.get('xp_por_mensagem', 5000)} XP\n"
                      f"• **Voz**: {self.config_data.get('xp_por_voz', 15000)} XP (a cada {self.config_data.get('voice_xp_interval_s', 300)}s)\n\n"
                      f"Para editar, use: `!config-xp`",
                inline=False
            )

        elif self.step == 8:
            admin_ping_ids = self.config_data.get('admin_ping_ids', [])
            admin_mention = ", ".join([f"<@&{rid}>" for rid in admin_ping_ids]) if admin_ping_ids else "Nenhum"
            embed.add_field(
                name="🔔 Papéis de Notificação",
                value=f"Papéis que serão mencionados para notificações importantes.\n\n"
                      f"**Papéis**: {admin_mention}\n\n"
                      f"Para editar, use: `!config-cargos`",
                inline=False
            )

        elif self.step == 9:
            embed.add_field(
                name="✅ Resumo",
                value="Revisar todas as configurações acima.\n\n"
                      "Você pode:\n"
                      "• Navegar pelos passos anteriores para ajustar valores\n"
                      "• Clicar em 'Salvar Configurações' para confirmar\n"
                      "• Usar comandos específicos para edições avançadas",
                inline=False
            )

        embed.set_footer(text=f"Passo {self.step} de {self.total_steps}")
        return embed

    def _format_channel(self, channel_id) -> str:
        """Formata o ID do canal para exibição."""
        if not channel_id:
            return "❌ Não configurado"
        guild = self.bot.get_guild(self.guild_id)
        if guild:
            channel = guild.get_channel(channel_id)
            if channel:
                return f"<#{channel_id}>"
        return f"❌ Canal inválido ({channel_id})"

    async def save_config(self, interaction: discord.Interaction):
        """Salva as configurações no banco de dados."""
        if not self.bot.db:
            await interaction.followup.send("❌ Banco de dados não disponível.", ephemeral=True)
            return

        try:
            async with self.bot.db.acquire() as conn:
                query = """
                    UPDATE server_config
                    SET commands_channel_id = $2,
                        status_channel_id = $3,
                        help_channel_id = $4,
                        antispam_log_channel_id = $5,
                        antinuke_log_channel_id = $6,
                        pix_channel_id = $7,
                        colors_channel_id = $8,
                        coins_log_channel_id = $9,
                        xp_log_channel_id = $10,
                        levelup_channel_id = $11,
                        ticket_support_category_id = $12,
                        ticket_donation_category_id = $13,
                        voice_creator_channel_id = $14,
                        adventure_log_channel_id = $15,
                        guild_raid_channel_id = $16,
                        premium_prices = $17::jsonb,
                        premium_multipliers = $18::jsonb,
                        daily_coins = $19,
                        daily_streak_bonus = $20,
                        coins_por_mensagem = $21,
                        coins_por_voz = $22,
                        xp_por_mensagem = $23,
                        xp_por_voz = $24,
                        voice_xp_interval_s = $25,
                        bonus_coins_por_nivel = $26,
                        admin_ping_ids = $27,
                        updated_at = NOW()
                    WHERE guild_id = $1
                """

                premium_prices = self.config_data.get('premium_prices', {})
                premium_multipliers = self.config_data.get('premium_multipliers', {})

                await conn.execute(
                    query,
                    self.guild_id,
                    self.config_data.get('commands_channel_id'),
                    self.config_data.get('status_channel_id'),
                    self.config_data.get('help_channel_id'),
                    self.config_data.get('antispam_log_channel_id'),
                    self.config_data.get('antinuke_log_channel_id'),
                    self.config_data.get('pix_channel_id'),
                    self.config_data.get('colors_channel_id'),
                    self.config_data.get('coins_log_channel_id'),
                    self.config_data.get('xp_log_channel_id'),
                    self.config_data.get('levelup_channel_id'),
                    self.config_data.get('ticket_support_category_id'),
                    self.config_data.get('ticket_donation_category_id'),
                    self.config_data.get('voice_creator_channel_id'),
                    self.config_data.get('adventure_log_channel_id'),
                    self.config_data.get('guild_raid_channel_id'),
                    premium_prices,
                    premium_multipliers,
                    self.config_data.get('daily_coins', 10000),
                    self.config_data.get('daily_streak_bonus', 10000),
                    self.config_data.get('coins_por_mensagem', 5000),
                    self.config_data.get('coins_por_voz', 15000),
                    self.config_data.get('xp_por_mensagem', 5000),
                    self.config_data.get('xp_por_voz', 15000),
                    self.config_data.get('voice_xp_interval_s', 300),
                    self.config_data.get('bonus_coins_por_nivel', 50000),
                    self.config_data.get('admin_ping_ids', []),
                )

            # Invalidate cache
            from db.config import refresh_server_config
            await refresh_server_config(self.bot.db, self.guild_id)

            # Emit NOTIFY for other processes
            async with self.bot.db.acquire() as conn:
                await conn.execute(
                    "SELECT pg_notify('fenrir_cache', $1)",
                    f"config:{self.guild_id}"
                )

            embed = discord.Embed(
                title="✅ Configurações Salvas",
                description="Todas as configurações foram salvas com sucesso!",
                color=discord.Color.green()
            )
            try:
                await interaction.edit_original_response(embed=embed, view=None)
            except:
                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except:
                    pass

        except Exception as e:
            log.error(f"Erro ao salvar configurações: {e}")
            try:
                embed = discord.Embed(
                    title="❌ Erro ao Salvar",
                    description=f"Erro: {e}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=None)
            except:
                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except:
                    pass


class ConfigBotCog(commands.Cog):
    """Sistema de configuração interativa do bot."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="config-bot")
    @commands.has_permissions(administrator=True)
    async def config_bot(self, ctx: commands.Context):
        """Inicia o wizard interativo de configuração."""

        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        loading_embed = discord.Embed(
            title="⚙️ Carregando Configuração...",
            description="Aguarde enquanto carregamos as configurações da guild.",
            color=discord.Color.blurple()
        )

        try:
            msg = await ctx.send(embed=loading_embed)
        except Exception as e:
            log.error(f"Erro ao responder: {e}")
            return

        try:
            from db.config import load_server_config

            config = await load_server_config(self.bot.db, ctx.guild.id)
            if not config:
                await msg.edit(
                    embed=discord.Embed(
                        title="❌ Erro",
                        description="Configuração da guild não encontrada.",
                        color=discord.Color.red()
                    ),
                    view=None
                )
                return

            config_data = config.to_dict()
            view = ConfigBotView(self.bot, ctx.guild.id, config_data, 1, 9)
            step_embed = await view.get_step_embed()

            await msg.edit(embed=step_embed, view=view)

        except Exception as e:
            log.error(f"Erro ao iniciar config-bot: {e}")
            try:
                await msg.edit(
                    embed=discord.Embed(
                        title="❌ Erro",
                        description=f"Erro ao carregar: {e}",
                        color=discord.Color.red()
                    ),
                    view=None
                )
            except Exception as edit_err:
                log.error(f"Erro ao editar mensagem de erro: {edit_err}")


    @commands.command(name="config-canais-log")
    @commands.has_permissions(administrator=True)
    async def config_canais_log(
        self,
        ctx: commands.Context,
        commands_ch: discord.TextChannel = None,
        status: discord.TextChannel = None,
        help_ch: discord.TextChannel = None,
        antispam: discord.TextChannel = None,
        antinuke: discord.TextChannel = None
    ):
        """Edita canais de log."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        try:
            async with self.bot.db.acquire() as conn:
                updates = []
                params = [ctx.guild.id]
                idx = 2

                if commands_ch:
                    updates.append(f"commands_channel_id = ${idx}")
                    params.append(commands_ch.id)
                    idx += 1

                if status:
                    updates.append(f"status_channel_id = ${idx}")
                    params.append(status.id)
                    idx += 1

                if help_ch:
                    updates.append(f"help_channel_id = ${idx}")
                    params.append(help_ch.id)
                    idx += 1

                if antispam:
                    updates.append(f"antispam_log_channel_id = ${idx}")
                    params.append(antispam.id)
                    idx += 1

                if antinuke:
                    updates.append(f"antinuke_log_channel_id = ${idx}")
                    params.append(antinuke.id)
                    idx += 1

                if not updates:
                    await ctx.send("⚠️ Nenhum canal foi especificado.")
                    return

                updates.append("updated_at = NOW()")
                query = f"UPDATE server_config SET {', '.join(updates)} WHERE guild_id = $1"
                await conn.execute(query, *params)

                from db.config import refresh_server_config
                await refresh_server_config(self.bot.db, ctx.guild.id)

                async with self.bot.db.acquire() as conn:
                    await conn.execute(
                        "SELECT pg_notify('fenrir_cache', $1)",
                        f"config:{ctx.guild.id}"
                    )

            embed = discord.Embed(
                title="✅ Canais de Log Atualizados",
                description="Canais foram configurados com sucesso!",
                color=discord.Color.green()
            )
            if commands_ch:
                embed.add_field(name="📢 Commands", value=commands_ch.mention, inline=True)
            if status:
                embed.add_field(name="📊 Status", value=status.mention, inline=True)
            if help_ch:
                embed.add_field(name="❓ Help", value=help_ch.mention, inline=True)
            if antispam:
                embed.add_field(name="🚫 Antispam", value=antispam.mention, inline=True)
            if antinuke:
                embed.add_field(name="☢️ Antinuke", value=antinuke.mention, inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            log.error(f"Erro ao configurar canais de log: {e}")
            await ctx.send(f"❌ Erro: {e}")

    @commands.command(name="config-canais-embeds")
    @commands.has_permissions(administrator=True)
    async def config_canais_embeds(
        self,
        ctx: commands.Context,
        pix: discord.TextChannel = None,
        ticket: discord.TextChannel = None,
        cores: discord.TextChannel = None,
        entrada: discord.TextChannel = None,
        saida: discord.TextChannel = None,
    ):
        """Edita os canais das embeds fixas (pix/ticket/cores) e logs de entrada/saída."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        try:
            async with self.bot.db.acquire() as conn:
                updates = []
                params = [ctx.guild.id]
                idx = 2

                if pix:
                    updates.append(f"pix_channel_id = ${idx}")
                    params.append(pix.id)
                    idx += 1

                if ticket:
                    updates.append(f"tickets_channel_id = ${idx}")
                    params.append(ticket.id)
                    idx += 1

                if cores:
                    updates.append(f"colors_channel_id = ${idx}")
                    params.append(cores.id)
                    idx += 1

                if entrada:
                    updates.append(f"member_join_log_channel_id = ${idx}")
                    params.append(entrada.id)
                    idx += 1

                if saida:
                    updates.append(f"member_leave_log_channel_id = ${idx}")
                    params.append(saida.id)
                    idx += 1

                if not updates:
                    await ctx.send("⚠️ Nenhum canal foi especificado.")
                    return

                updates.append("updated_at = NOW()")
                query = f"UPDATE server_config SET {', '.join(updates)} WHERE guild_id = $1"
                await conn.execute(query, *params)

                from db.config import refresh_server_config
                await refresh_server_config(self.bot.db, ctx.guild.id)

                async with self.bot.db.acquire() as conn:
                    await conn.execute(
                        "SELECT pg_notify('fenrir_cache', $1)",
                        f"config:{ctx.guild.id}"
                    )

            embed = discord.Embed(
                title="✅ Canais de Embeds Atualizados",
                description="As embeds de pix/ticket/cores são (re)postadas nesses canais no próximo boot do bot.",
                color=discord.Color.green()
            )
            if pix:
                embed.add_field(name="💎 Pix", value=pix.mention, inline=True)
            if ticket:
                embed.add_field(name="🎫 Ticket", value=ticket.mention, inline=True)
            if cores:
                embed.add_field(name="🎨 Cores", value=cores.mention, inline=True)
            if entrada:
                embed.add_field(name="👋 Entrada", value=entrada.mention, inline=True)
            if saida:
                embed.add_field(name="🚪 Saída", value=saida.mention, inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            log.error(f"Erro ao configurar canais de embeds: {e}")
            await ctx.send(f"❌ Erro: {e}")

    @commands.command(name="config-economia")
    @commands.has_permissions(administrator=True)
    async def config_economia(
        self,
        ctx: commands.Context,
        daily: int = None,
        bonus_daily: int = None,
        mensagem: int = None,
        voz: int = None,
        nivel: int = None
    ):
        """Edita ganhos de coins."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        try:
            async with self.bot.db.acquire() as conn:
                updates = []
                params = [ctx.guild.id]
                idx = 2

                if daily is not None:
                    updates.append(f"daily_coins = ${idx}")
                    params.append(daily)
                    idx += 1

                if bonus_daily is not None:
                    updates.append(f"daily_streak_bonus = ${idx}")
                    params.append(bonus_daily)
                    idx += 1

                if mensagem is not None:
                    updates.append(f"coins_por_mensagem = ${idx}")
                    params.append(mensagem)
                    idx += 1

                if voz is not None:
                    updates.append(f"coins_por_voz = ${idx}")
                    params.append(voz)
                    idx += 1

                if nivel is not None:
                    updates.append(f"bonus_coins_por_nivel = ${idx}")
                    params.append(nivel)
                    idx += 1

                if not updates:
                    await ctx.send("⚠️ Nenhum valor foi especificado.")
                    return

                updates.append("updated_at = NOW()")
                query = f"UPDATE server_config SET {', '.join(updates)} WHERE guild_id = $1"
                await conn.execute(query, *params)

                from db.config import refresh_server_config
                await refresh_server_config(self.bot.db, ctx.guild.id)

                async with self.bot.db.acquire() as conn:
                    await conn.execute(
                        "SELECT pg_notify('fenrir_cache', $1)",
                        f"config:{ctx.guild.id}"
                    )

            embed = discord.Embed(
                title="✅ Ganhos de Coins Atualizados",
                color=discord.Color.green()
            )
            if daily is not None:
                embed.add_field(name="💰 Daily", value=f"{daily} coins", inline=True)
            if bonus_daily is not None:
                embed.add_field(name="⭐ Bonus Streak", value=f"{bonus_daily} coins", inline=True)
            if mensagem is not None:
                embed.add_field(name="💬 Por Mensagem", value=f"{mensagem} coins", inline=True)
            if voz is not None:
                embed.add_field(name="🔊 Por Voz", value=f"{voz} coins", inline=True)
            if nivel is not None:
                embed.add_field(name="📈 Por Level", value=f"{nivel} coins", inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            log.error(f"Erro ao configurar economia: {e}")
            await ctx.send(f"❌ Erro: {e}")

    @commands.command(name="config-xp")
    @commands.has_permissions(administrator=True)
    async def config_xp(
        self,
        ctx: commands.Context,
        mensagem: int = None,
        voz: int = None,
        intervalo: int = None
    ):
        """Edita ganhos de XP."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        try:
            async with self.bot.db.acquire() as conn:
                updates = []
                params = [ctx.guild.id]
                idx = 2

                if mensagem is not None:
                    updates.append(f"xp_por_mensagem = ${idx}")
                    params.append(mensagem)
                    idx += 1

                if voz is not None:
                    updates.append(f"xp_por_voz = ${idx}")
                    params.append(voz)
                    idx += 1

                if intervalo is not None:
                    updates.append(f"voice_xp_interval_s = ${idx}")
                    params.append(intervalo)
                    idx += 1

                if not updates:
                    await ctx.send("⚠️ Nenhum valor foi especificado.")
                    return

                updates.append("updated_at = NOW()")
                query = f"UPDATE server_config SET {', '.join(updates)} WHERE guild_id = $1"
                await conn.execute(query, *params)

                from db.config import refresh_server_config
                await refresh_server_config(self.bot.db, ctx.guild.id)

                async with self.bot.db.acquire() as conn:
                    await conn.execute(
                        "SELECT pg_notify('fenrir_cache', $1)",
                        f"config:{ctx.guild.id}"
                    )

            embed = discord.Embed(
                title="✅ Ganhos de XP Atualizados",
                color=discord.Color.green()
            )
            if mensagem is not None:
                embed.add_field(name="💬 Por Mensagem", value=f"{mensagem} XP", inline=True)
            if voz is not None:
                embed.add_field(name="🔊 Por Minuto em Voz", value=f"{voz} XP", inline=True)
            if intervalo is not None:
                embed.add_field(name="⏱️ Intervalo", value=f"{intervalo} segundos", inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            log.error(f"Erro ao configurar XP: {e}")
            await ctx.send(f"❌ Erro: {e}")

    @commands.command(name="config-premium")
    @commands.has_permissions(administrator=True)
    async def config_premium(
        self,
        ctx: commands.Context,
        aventureiro: int = None,
        lendario: int = None,
        mitico: int = None
    ):
        """Edita preços dos planos premium."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        try:
            from db.config import load_server_config

            config = await load_server_config(self.bot.db, ctx.guild.id)
            if not config:
                await ctx.send("❌ Configuração não encontrada.")
                return

            prices = dict(config.get('premium_prices', {}))

            if aventureiro is not None:
                prices['aventureiro'] = aventureiro
            if lendario is not None:
                prices['lendario'] = lendario
            if mitico is not None:
                prices['mitico'] = mitico

            async with self.bot.db.acquire() as conn:
                await conn.execute(
                    "UPDATE server_config SET premium_prices = $1::jsonb, updated_at = NOW() WHERE guild_id = $2",
                    prices,
                    ctx.guild.id
                )

                from db.config import refresh_server_config
                await refresh_server_config(self.bot.db, ctx.guild.id)

                await conn.execute(
                    "SELECT pg_notify('fenrir_cache', $1)",
                    f"config:{ctx.guild.id}"
                )

            embed = discord.Embed(
                title="✅ Preços Premium Atualizados",
                color=discord.Color.green()
            )
            embed.add_field(name="⭐ Aventureiro", value=f"R$ {prices.get('aventureiro', 0)}", inline=True)
            embed.add_field(name="🌟 Lendário", value=f"R$ {prices.get('lendario', 0)}", inline=True)
            embed.add_field(name="✨ Mítico", value=f"R$ {prices.get('mitico', 0)}", inline=True)

            await ctx.send(embed=embed)

        except Exception as e:
            log.error(f"Erro ao configurar premium: {e}")
            await ctx.send(f"❌ Erro: {e}")

    # ─── Persistência genérica ────────────────────────────────────────────────

    async def _persist_config(self, guild_id: int, fields: dict) -> None:
        """Aplica um UPDATE parcial em server_config, invalida cache e emite NOTIFY.

        `fields` mapeia coluna → valor. Os nomes de coluna vêm sempre de um
        conjunto interno fixo (nunca de input do usuário), então a interpolação
        no SET é segura. Colunas array (BIGINT[]) recebem list[int] e são
        mapeadas nativamente pelo asyncpg.
        """
        cols = list(fields.keys())
        set_clause = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(cols))
        params = [guild_id, *[fields[c] for c in cols]]
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                f"UPDATE server_config SET {set_clause}, updated_at = NOW() WHERE guild_id = $1",
                *params,
            )
            await conn.execute(
                "SELECT pg_notify('fenrir_cache', $1)", f"config:{guild_id}"
            )

        from db.config import refresh_server_config
        await refresh_server_config(self.bot.db, guild_id)

    @commands.command(name="config-canais-sistemas")
    @commands.has_permissions(administrator=True)
    async def config_canais_sistemas(
        self,
        ctx: commands.Context,
        voz_criador: discord.VoiceChannel = None,
        raids: discord.TextChannel = None,
        aventuras: discord.TextChannel = None,
        coins_log: discord.TextChannel = None,
        xp_log: discord.TextChannel = None,
        levelup: discord.TextChannel = None,
        premium_categoria: discord.CategoryChannel = None,
        premium_log: discord.TextChannel = None,
    ):
        """Persiste os canais que hoje dependem de IDs padrão hardcoded."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        fields = {}
        if voz_criador:
            fields["voice_creator_channel_id"] = voz_criador.id
        if raids:
            fields["guild_raid_channel_id"] = raids.id
        if aventuras:
            fields["adventure_log_channel_id"] = aventuras.id
        if coins_log:
            fields["coins_log_channel_id"] = coins_log.id
        if xp_log:
            fields["xp_log_channel_id"] = xp_log.id
        if levelup:
            fields["levelup_channel_id"] = levelup.id
        if premium_categoria:
            fields["premium_payment_category_id"] = premium_categoria.id
        if premium_log:
            fields["premium_log_channel_id"] = premium_log.id

        if not fields:
            await ctx.send("⚠️ Nenhum canal foi especificado.")
            return

        try:
            await self._persist_config(ctx.guild.id, fields)
        except Exception as e:
            log.error(f"Erro ao configurar canais de sistemas: {e}")
            await ctx.send(f"❌ Erro: {e}")
            return

        embed = discord.Embed(
            title="✅ Canais de Sistemas Atualizados",
            color=discord.Color.green(),
        )
        if voz_criador:
            embed.add_field(name="🔊 Criador de Salas", value=voz_criador.mention, inline=True)
        if raids:
            embed.add_field(name="⚔️ Raids", value=raids.mention, inline=True)
        if aventuras:
            embed.add_field(name="🗺️ Aventuras", value=aventuras.mention, inline=True)
        if coins_log:
            embed.add_field(name="💰 Coins Log", value=coins_log.mention, inline=True)
        if xp_log:
            embed.add_field(name="⭐ XP Log", value=xp_log.mention, inline=True)
        if levelup:
            embed.add_field(name="📈 Level Up", value=levelup.mention, inline=True)
        if premium_categoria:
            embed.add_field(name="💳 Categoria Pix", value=premium_categoria.mention, inline=True)
        if premium_log:
            embed.add_field(name="💎 Premium Log", value=premium_log.mention, inline=True)

        await ctx.send(embed=embed)

    _CARGOS_TIPO_LABELS = {
        "free_color_role_ids": "Cores gratuitas",
        "premium_color_role_ids": "Cores premium",
        "special_access_role_ids": "Acesso especial",
        "admin_ping_ids": "Ping de admins",
    }

    @commands.command(name="config-cargos")
    @commands.has_permissions(administrator=True)
    async def config_cargos(
        self,
        ctx: commands.Context,
        tipo: Literal["free_color_role_ids", "premium_color_role_ids", "special_access_role_ids", "admin_ping_ids"],
        modo: Literal["substituir", "adicionar", "remover"],
        cargo1: discord.Role = None,
        cargo2: discord.Role = None,
        cargo3: discord.Role = None,
        cargo4: discord.Role = None,
        cargo5: discord.Role = None,
    ):
        """Persiste os arrays de cargos (BIGINT[]) que hoje ficam vazios ou hardcoded."""
        if not self.bot.db:
            await ctx.send("❌ Banco de dados não disponível.")
            return

        coluna = tipo
        selecionados = [c.id for c in (cargo1, cargo2, cargo3, cargo4, cargo5) if c]
        if not selecionados:
            await ctx.send("⚠️ Nenhum cargo foi especificado.")
            return

        try:
            from db.config import load_server_config

            config = await load_server_config(self.bot.db, ctx.guild.id)
            atuais = list(config.get(coluna) or []) if config else []

            if modo == "substituir":
                nova = selecionados
            elif modo == "adicionar":
                nova = atuais + [rid for rid in selecionados if rid not in atuais]
            else:  # remover
                nova = [rid for rid in atuais if rid not in selecionados]

            await self._persist_config(ctx.guild.id, {coluna: nova})
        except Exception as e:
            log.error(f"Erro ao configurar cargos ({coluna}): {e}")
            await ctx.send(f"❌ Erro: {e}")
            return

        cargos_txt = ", ".join(f"<@&{rid}>" for rid in nova) if nova else "*(nenhum)*"
        embed = discord.Embed(
            title="✅ Cargos Atualizados",
            description=f"**{self._CARGOS_TIPO_LABELS.get(tipo, tipo)}** — modo **{modo}**",
            color=discord.Color.green(),
        )
        embed.add_field(name="Lista atual", value=cargos_txt, inline=False)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ConfigBotCog(bot))
