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
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        COGS_DIR = os.path.join(BASE_DIR, "cogs")

        cont = 1
        for entry in os.listdir(COGS_DIR):
            if entry.startswith("_"):
                continue
            if entry.endswith(".py"):
                await self.load_extension(f"cogs.{entry[:-3]}")
                print(cont)
                cont += 1
            elif os.path.isdir(os.path.join(COGS_DIR, entry)):
                if os.path.exists(os.path.join(COGS_DIR, entry, "__init__.py")):
                    await self.load_extension(f"cogs.{entry}")
                    print(cont)
                    cont += 1

        await self.tree.sync()
        print("✅ Sync completo")

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