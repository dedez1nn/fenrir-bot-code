import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import traceback

class FenrirBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        COGS_DIR = os.path.join(BASE_DIR, "cogs")

        for root, dirs, files in os.walk(COGS_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for filename in files:
                if filename.endswith(".py") and filename != "__init__.py":
                    rel = os.path.relpath(os.path.join(root, filename), BASE_DIR)
                    module = rel.replace(os.sep, ".")[:-3]
                    await self.load_extension(module)

        await self.tree.sync()
        print("Bot setup loaded")

    async def on_ready(self):
        print(f"🤖 Bot conectado como {self.user} (ID: {self.user.id})")

        await self.change_presence(
    activity=discord.Streaming(
            name='Relaxando na Alcateia do Fenrir 🐺',
            url='https://www.twitch.tv/discord'
        )
    )
        
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
        
        cores_cog = self.get_cog("EnviarCores")
        if cores_cog:
            canal_cores = self.get_channel(1428161467286421524)
            if canal_cores:
                deleted_count = 0
                async for message in canal_cores.history(limit=10):
                    if message.author == self.user:
                        await message.delete()
                        deleted_count += 1
                        await asyncio.sleep(0.5)
                await cores_cog.cores(canal_cores)
                
        pix_cog = self.get_cog("PixCog")
        canal_pix = self.get_channel(1429555260917284947)
        if pix_cog:
            deleted_count = 0
            async for message in canal_pix.history(limit=10):
                if message.author == self.user:
                    await message.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.5)
            await pix_cog.setup_planos_embed(canal_pix)
            
        ticket_cog = self.get_cog("TicketCog")
        canal_ticket = self.get_channel(1426275563378839606)
        if ticket_cog:
            deleted_count = 0
            async for message in canal_ticket.history(limit=10):
                if message.author == self.user:
                    await message.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.5)
            await ticket_cog.ticket(canal_ticket)
            
            
bot = FenrirBot()

@bot.tree.command(name="ping", description="Mostra a latência do bot")
async def ping(interaction: discord.Interaction):
    
    if interaction.channel.id != 1426205118293868748 and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
        return
    
    latencia = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência: **{latencia}ms**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)
    


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    traceback.print_exception(type(error), error, error.__traceback__)
    msg = "❌ Ocorreu um erro inesperado. Tente novamente mais tarde."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


load_dotenv()
TOKEN = os.getenv("TOKEN")

async def main():
    await bot.start(TOKEN)  

asyncio.run(main())