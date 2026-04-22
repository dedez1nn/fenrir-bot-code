import discord
from discord.ext import commands

class AutoRemoveBots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            if member.id == self.bot.user.id:
                return

            await member.kick(reason="Bot não autorizado automaticamente removido.")

async def setup(bot):
    await bot.add_cog(AutoRemoveBots(bot))
