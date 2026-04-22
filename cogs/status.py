import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime


class StatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.status_canal = 1427311999381147708

    async def status(self, canal):
        if canal is None and hasattr(self, 'status_canal'):
            canal = self.bot.get_channel(self.status_canal)
        
        canal_changelog = self.bot.get_channel(1427311999381147708)
        embed = discord.Embed(
            title="🤖 Status do Bot",
            description="Olá, pessoal! Estou **on-line**, interagindo\n"
                        "com vocês e de olho nos próximos passos! 🎉\n"
                        f"confira as minhas alterações em {canal_changelog.mention if canal_changelog else 'canal não encontrado'}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        agora = int(datetime.now().timestamp())
        embed.add_field(name="⚙️ Versão:", value="`2.0.0`", inline=True)
        embed.add_field(name="🔌 Status:", value="`On-line`", inline=False)
        embed.add_field(name="⌛ Latência:", value=f"`{round(self.bot.latency * 1000)}ms`", inline=False)
        embed.add_field(name="🖥️ Programador Responsável:", value="`dedez1n1`", inline=False)
        embed.add_field(name="🕰️ Última vez off-line:", value=f"<t:{agora}:R>", inline=True)

        if self.bot.user.display_avatar:
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
        else:
            embed.set_author(name=self.bot.user.name)

        embed.set_footer(text="© 2025 ALCATEIA DO FENRIR. Todos os direitos reservados.")

        await canal.send(embed=embed)
        
    @app_commands.command(name="manutencao", description="Envia mensagem de reinício (DEVS).")
    async def reiniciando(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem usar este comando!", ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🤖 Status do Bot",
            description="Olá, pessoal! Estarei **off-line** nos próximos minutos\n"
                        "enquanto isso, deem uma relaxada, porque jajá estou 🎉\n"
                        f"de volta! Informarei assim que estiver **on-line**.\n\n"
                        "**Motivo**: Manutenção.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        agora = int(datetime.now().timestamp())
        embed.add_field(name="⚙️ Versão:", value="`2.0.0`", inline=True)
        embed.add_field(name="🔌 Status:", value="`Off-line`", inline=False)
        embed.add_field(name="🖥️ Programador Responsável:", value="`dedez1n1`", inline=False)
        embed.add_field(name="🕰️ Última vez on-line:", value=f"<t:{agora}:R>", inline=True)

        if self.bot.user.display_avatar:
            embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
        else:
            embed.set_author(name=self.bot.user.name)
            
        embed.set_footer(text="© 2025 ALCATEIA DO FENRIR. Todos os direitos reservados.")

        await interaction.response.send_message(embed=embed)                        

async def setup(bot: commands.Bot):
    await bot.add_cog(StatusCog(bot))
