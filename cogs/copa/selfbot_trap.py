"""Cog Armadilha de Selfbot — detecção e resposta automática."""

import asyncio
import logging
import time
from collections import defaultdict, deque

import discord
from discord.ext import commands

from repositories.server_channels import (
    get_all_selfbot_channels,
    get_all_selfbot_log_channels,
    remove_selfbot_channel,
    remove_selfbot_log_channel,
    set_selfbot_channel,
    set_selfbot_log_channel,
)

logger = logging.getLogger(__name__)

# Janela de tempo para varredura de mensagens suspeitas (segundos)
SWEEP_WINDOW = 15

# Cache de mensagens recentes: user_id -> deque de (guild_id, channel_id, message_id, timestamp)
_recent: dict[int, deque] = defaultdict(lambda: deque(maxlen=100))

# Canal trap por guild: guild_id -> channel_id (cache em memória)
_trap_channels: dict[int, int] = {}
_log_channels: dict[int, int] = {}


class SelfbotTrapCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        global _trap_channels, _log_channels

        if self.bot.db is None:
            logger.warning("bot.db indisponível — armadilha de selfbot em modo local (data/local_config.json).")
            from db.local_config import get as local_get

            guild_id = local_get("selfbot_trap_guild_id")
            if guild_id is None:
                return
            trap_channel_id = local_get("selfbot_trap_channel_id")
            log_channel_id = local_get("selfbot_log_channel_id")
            if trap_channel_id is not None:
                _trap_channels[guild_id] = trap_channel_id
            if log_channel_id is not None:
                _log_channels[guild_id] = log_channel_id
            return

        _trap_channels = await get_all_selfbot_channels(self.bot.db)
        _log_channels = await get_all_selfbot_log_channels(self.bot.db)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return

        guild_id = message.guild.id
        trap_channel_id = _trap_channels.get(guild_id)

        # Registra mensagem no cache de todos os servidores com trap ativo
        if trap_channel_id is not None:
            _recent[message.author.id].append((
                guild_id,
                message.channel.id,
                message.id,
                time.time(),
            ))

        # Se a mensagem foi enviada no canal armadilha → acionar trap
        if trap_channel_id is not None and message.channel.id == trap_channel_id:
            await self._trigger_trap(message)

    async def _trigger_trap(self, message: discord.Message) -> None:
        guild = message.guild
        member = message.author

        logger.warning(
            "Selfbot detectado: %s (%s) em %s/%s",
            member, member.id, guild.name, message.channel.name,
        )

        try:
            await message.delete()
        except discord.Forbidden:
            logger.warning("Sem permissão para deletar mensagem do canal armadilha")
        except Exception:
            logger.exception("Erro ao deletar mensagem do canal armadilha")

        now = time.time()
        to_delete: list[tuple[int, int]] = []
        for entry in list(_recent[member.id]):
            g_id, ch_id, msg_id, ts = entry
            if g_id != guild.id:
                continue
            if ch_id == message.channel.id:
                continue
            if now - ts <= SWEEP_WINDOW:
                to_delete.append((ch_id, msg_id))

        if to_delete:
            logger.info("Varrendo %d mensagens recentes de %s em outros canais", len(to_delete), member)
            for ch_id, msg_id in to_delete:
                ch = guild.get_channel(ch_id)
                if ch is None:
                    continue
                try:
                    msg = await ch.fetch_message(msg_id)
                    await msg.delete()
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    logger.warning("Sem permissão para deletar mensagem em %s", ch.name)
                except Exception:
                    logger.exception("Erro ao deletar mensagem no sweep")

        _recent.pop(member.id, None)

        kicked = False
        if isinstance(member, discord.Member):
            try:
                await member.kick(reason="Selfbot detectado: enviou mensagem em canal armadilha")
                kicked = True
                logger.info("Usuário %s kickado por selfbot em %s", member, guild.name)
            except discord.Forbidden:
                logger.warning("Sem permissão para kickar %s em %s", member, guild.name)
            except Exception:
                logger.exception("Erro ao kickar usuário selfbot")

        # Envia log no canal configurado ou fallback para canal do sistema
        log_channel_id = _log_channels.get(guild.id)
        log_ch = self.bot.get_channel(log_channel_id) if log_channel_id else guild.system_channel

        if log_ch:
            try:
                if log_channel_id:
                    embed = discord.Embed(
                        title="🚨 Selfbot Detectado",
                        color=0xFF4444,
                        timestamp=discord.utils.utcnow(),
                    )
                    embed.add_field(name="Usuário", value=f"{member} (`{member.id}`)", inline=True)
                    embed.add_field(name="Canal armadilha", value=message.channel.mention, inline=True)
                    embed.add_field(name="Mensagens varridas", value=str(len(to_delete)), inline=True)
                    embed.add_field(name="Ação", value="✅ Kickado" if kicked else "⚠️ Sem permissão para kickar", inline=True)
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await log_ch.send(embed=embed)
                else:
                    await log_ch.send(
                        f"🚨 **Selfbot detectado e removido:** `{member}` ({member.id})\n"
                        f"Kickado automaticamente. {len(to_delete)} mensagem(ns) apagada(s) em outros canais."
                    )
            except Exception:
                logger.exception("Erro ao enviar log de selfbot")

    # ── Slash commands ────────────────────────────────────────────────────────

    @commands.command(name="config-selfbot")
    @commands.has_permissions(administrator=True)
    async def cmd_config_selfbot(
        self,
        ctx: commands.Context,
        canal: discord.TextChannel,
        canal_log: discord.TextChannel | None = None,
    ) -> None:
        guild_id = ctx.guild.id

        if self.bot.db is not None:
            await set_selfbot_channel(self.bot.db, guild_id, canal.id)
            if canal_log:
                await set_selfbot_log_channel(self.bot.db, guild_id, canal_log.id)
        else:
            from db.local_config import set_many

            fields = {"selfbot_trap_guild_id": guild_id, "selfbot_trap_channel_id": canal.id}
            if canal_log:
                fields["selfbot_log_channel_id"] = canal_log.id
            set_many(fields)

        _trap_channels[guild_id] = canal.id
        if canal_log:
            _log_channels[guild_id] = canal_log.id

        aviso_local = "" if self.bot.db else "\n⚠️ Sem Postgres — salvo localmente (`data/local_config.json`), só vale para esta instância."
        embed = discord.Embed(
            title="🚨 Armadilha de Selfbot Configurada",
            description=aviso_local or None,
            color=0xFF4444,
        )
        embed.add_field(name="Canal armadilha", value=canal.mention, inline=True)

        if canal_log:
            embed.add_field(name="Canal de log", value=canal_log.mention, inline=True)

        embed.add_field(
            name="Como funciona",
            value=(
                "Qualquer usuário que enviar uma mensagem no canal armadilha será **kickado automaticamente**.\n"
                f"O bot também varre mensagens dos últimos **{SWEEP_WINDOW}s** em outros canais e as apaga.\n\n"
                "⚠️ Não envie mensagens no canal armadilha!"
            ),
            inline=False,
        )
        embed.set_footer(text="Use !selfbot-status para ver a configuração atual")
        await ctx.send(embed=embed)

    @commands.command(name="selfbot-remover")
    @commands.has_permissions(administrator=True)
    async def cmd_selfbot_remover(self, ctx: commands.Context) -> None:
        guild_id = ctx.guild.id

        if self.bot.db is not None:
            await remove_selfbot_channel(self.bot.db, guild_id)
            await remove_selfbot_log_channel(self.bot.db, guild_id)
        else:
            from db.local_config import set_many

            set_many({
                "selfbot_trap_guild_id": None,
                "selfbot_trap_channel_id": None,
                "selfbot_log_channel_id": None,
            })

        _trap_channels.pop(guild_id, None)
        _log_channels.pop(guild_id, None)

        aviso_local = "" if self.bot.db else " (local)"
        await ctx.send(f"✅ Armadilha de selfbot e canal de log removidos{aviso_local}.")

    @commands.command(name="selfbot-status")
    @commands.has_permissions(administrator=True)
    async def cmd_selfbot_status(self, ctx: commands.Context) -> None:
        guild_id = ctx.guild.id
        channel_id = _trap_channels.get(guild_id)
        log_channel_id = _log_channels.get(guild_id)

        embed = discord.Embed(title="🚨 Status — Armadilha de Selfbot", color=0xFF4444)
        if not self.bot.db:
            embed.add_field(
                name="⚠️ Modo",
                value="Sem Postgres — usando `data/local_config.json` (só vale para esta instância)",
                inline=False,
            )
        if channel_id:
            ch = ctx.guild.get_channel(channel_id)
            mention = ch.mention if ch else f"<canal removido: {channel_id}>"
            embed.add_field(name="Status", value="🟢 Ativo", inline=True)
            embed.add_field(name="Canal armadilha", value=mention, inline=True)
            embed.add_field(name="Janela de varredura", value=f"{SWEEP_WINDOW}s", inline=True)

            if log_channel_id:
                log_ch = ctx.guild.get_channel(log_channel_id)
                log_mention = log_ch.mention if log_ch else f"<canal removido: {log_channel_id}>"
                embed.add_field(name="Canal de log", value=log_mention, inline=True)
            else:
                embed.add_field(name="Canal de log", value="Canal do sistema (padrão)", inline=True)
        else:
            embed.add_field(name="Status", value="🔴 Inativo", inline=True)
            embed.description = "Use `!config-selfbot` para configurar."

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SelfbotTrapCog(bot))
