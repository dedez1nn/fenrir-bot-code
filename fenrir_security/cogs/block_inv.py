import re
import discord
from discord.ext import commands

class InviteBlocker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_pattern = re.compile(r"(discord\.gg/|discord\.com/invite/)(\w+)")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        matches = self.invite_pattern.findall(message.content)
        for match in matches:
            code = match[1]
            try:
                invite = await self.bot.fetch_invite(code)
                if invite.guild.id != message.guild.id:
                    if message.guild.me.guild_permissions.manage_messages:
                        await message.delete()
                        
                        embed = discord.Embed(
                            title="🚫 Convite de Outro Servidor Detectado",
                            description="Seu convite foi removido automaticamente.",
                            color=discord.Color.red()
                        )
                        embed.add_field(
                            name="📋 Regra Violada:",
                            value="Envio de convites de servidores externos",
                            inline=False
                        )
                        embed.add_field(
                            name="🌐 Servidor do Convite:",
                            value=f"`{invite.guild.name}`",
                            inline=True
                        )
                        embed.add_field(
                            name="💬 Canal:",
                            value=f"`{message.channel.name}`",
                            inline=True
                        )
                        embed.set_footer(
                            text=f"{message.guild.name} • Sistema Anti-Spam",
                            icon_url=message.guild.icon.url if message.guild.icon else None
                        )
                        
                        try:
                            await message.author.send(embed=embed)
                        except discord.Forbidden:
                            pass
                        else:
                            embed = discord.Embed(
                            title="⚠️ Aviso Importante",
                            description=f"**Atenção {message.author.mention}!**\n\nVocê enviou um convite de outro servidor em **{message.guild.name}**, mas não é permitido compartilhar convites externos aqui.",
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.add_field(
                            name="Servidor do convite:",
                            value=f"**{invite.guild.name}**",
                            inline=False
                        )
                        embed.add_field(
                            name="Ação:",
                            value="A mensagem foi apagada automaticamente",
                            inline=False
                        )
                        embed.set_footer(text="Sistema de Moderação")
                        
                        try:
                            await message.author.send(embed=embed)
                        except discord.Forbidden:
                            warning_msg = await message.channel.send(
                                f"{message.author.mention}, não é permitido enviar convites de outros servidores!",
                                delete_after=10
                            )
                        break
            except discord.NotFound:
                pass

async def setup(bot):
    await bot.add_cog(InviteBlocker(bot))