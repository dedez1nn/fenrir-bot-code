import discord
from dotenv import load_dotenv
from discord.ext import commands
import os
import asyncio

class FenrirBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=None, intents=intents)

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
        await self.tree.sync()
        print("✅ Comandos sincronizados com sucesso!")

    async def on_ready(self):
        print(f"🤖 Bot conectado como {self.user} (ID: {self.user.id})")
        
        await bot.change_presence(activity=discord.Streaming(name='Relaxando na Alcateia do Fenrir 🐺', url='https://www.twitch.tv/discord'))
        
        status_cog = self.get_cog("StatusCog")
        if status_cog:
            canal_status = self.get_channel(1427050535634075851)
            deleted_count = 0
            async for message in canal_status.history(limit=10):
                if message.author == self.user:
                    await message.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.5)
            await status_cog.status(canal_status)

bot = FenrirBot()

@bot.tree.command(name="ping", description="Mostra a latência do bot")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência: **{latency}ms**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

load_dotenv()
TOKEN = os.getenv("TOKEN")

async def main():
    await bot.start(TOKEN)  

asyncio.run(main())