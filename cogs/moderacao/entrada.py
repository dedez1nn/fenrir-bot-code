import discord
from discord.ext import commands
import json
import os

_DEFAULT_JOIN_LOG_CH  = 1426206240467320983
_DEFAULT_HELP_CH      = 1426274988046155787
_DEFAULT_LEAVE_LOG_CH = 1427472688665854133


class MemberLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feature_enabled: bool = True

    async def cog_load(self) -> None:
        if self.bot.db is not None:
            cfg = getattr(self.bot, "config", None)
            guild_id = (cfg.get("guild_id") if cfg else None)
            if guild_id:
                from db.feature_config import is_feature_enabled
                self.feature_enabled = await is_feature_enabled(self.bot.db, guild_id, "member_logs")

    async def reload_feature_state(self) -> None:
        await self.cog_load()

    async def validate_feature_config(self) -> list:
        from db.validators import validate_member_logs
        cfg = getattr(self.bot, "config", None)
        return validate_member_logs(cfg.to_dict() if cfg else {})

    def _cfg(self, key: str, default: int) -> int:
        c = getattr(self.bot, "config", None)
        return (c.get(key) if c else None) or default

    def carregar_xp(self):
        if os.path.exists(self.xp_file):
            with open(self.xp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def salvar_xp(self, dados):
        with open(self.xp_file, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.feature_enabled:
            return
        channel = member.guild.get_channel(self._cfg("member_join_log_channel_id", _DEFAULT_JOIN_LOG_CH))
        _cfg = getattr(self.bot, "config", None)
        _tickets_id = _cfg.get("tickets_channel_id") if _cfg else None
        ticket = member.guild.get_channel(_tickets_id) if _tickets_id else None
        duvidas = member.guild.get_channel(self._cfg("help_channel_id", _DEFAULT_HELP_CH))

        if channel:
            embed = discord.Embed(
                title="👋 Novo Membro!",
                description=(
                    f"Bem-vindo ao servidor {member.mention}!\n"
                    f"Aventure-se com meus comandos no Servidor!\n"
                    f"Para criar sua Guild, digite /guild_create (nome)\n"
                    f"Para mais informações, abra um ticket em {ticket.mention if ticket else 'tickets'},\n"
                    f"ou envie uma dúvida geral em {duvidas.mention}.\n"
                ),
                color=discord.Color.light_gray(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name="🐺 Fenrir BOT", icon_url="https://cdn.discordapp.com/attachments/1156734159457353848/1426287031922720868/Design_sem_nome_15.png?ex=68eaaccf&is=68e95b4f&hm=8dcb75de780ad5d8955bcd22d8c12bce3e8c5c92f2f18b6dae5006576f869e6a&")
            embed.set_image(url="https://cdn.discordapp.com/attachments/1156734159457353848/1426285299817779200/SEJA_BEM-VINDO_3.gif?ex=68eaab32&is=68e959b2&hm=b0aa37e920d8651f9095bd9e8c1815882332f9dadb95f0c8d4167199238d354f&")
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID do usuário: {member.id}")
            embed.set_footer(text="Entrada registrada automaticamente — Fenrir BOT")
            await channel.send(embed=embed)
            
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not self.feature_enabled:
            return
        canal = self.bot.get_channel(self._cfg("member_leave_log_channel_id", _DEFAULT_LEAVE_LOG_CH))
        if canal:
            embed = discord.Embed(
                title="👋 Saída de Membro!",
                description=f"O membro {member.mention} saiu do servidor.",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="*Membros no servidor*", value=f"{member.guild.member_count}", inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await canal.send(embed=embed)
            
        xp_data = self.carregar_xp()
        user_id = str(member.id)
        if user_id in xp_data:
            del xp_data[user_id]
            self.salvar_xp(xp_data)
        

async def setup(bot):
    await bot.add_cog(MemberLogs(bot))
