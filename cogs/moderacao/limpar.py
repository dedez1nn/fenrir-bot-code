import discord
from discord.ext import commands

class ClearMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="limpar")
    @commands.has_permissions(administrator=True)
    async def clear(self, ctx: commands.Context, mensagens: int):
        deleted = await ctx.channel.purge(limit=mensagens + 1)
        aviso = await ctx.send(f"✅ {len(deleted) - 1} mensagens apagadas!")
        await aviso.delete(delay=5)

async def setup(bot):
    await bot.add_cog(ClearMessages(bot))