import discord
from discord.ext import commands
import json
import os

class MemberLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1426206240467320983
        
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
        channel = member.guild.get_channel(self.log_channel_id)
        ticket = member.guild.get_channel(1426275563378839606)
        duvidas = member.guild.get_channel(1426274988046155787)

        if channel:
            embed = discord.Embed(
                title="👋 Novo Membro!",
                description=(
                    f"Bem-vindo ao servidor {member.mention}!\n"
                    f"Aventure-se com meus comandos no Servidor!\n"
                    f"Para criar sua Guild, digite /guild_create (nome)\n"
                    f"Para mais informações, abra um ticket em {ticket.mention},\n"
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
        canal = self.bot.get_channel(1427472688665854133)
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
