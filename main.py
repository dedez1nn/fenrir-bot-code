import discord
from dotenv import load_dotenv
from discord.ext import commands
import os
import asyncio

class FenrirBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="?", intents=intents)

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
    
    if interaction.channel.id != 1426205118293868748:
        await interaction.response.send_message(f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {bot.get_channel(1426205118293868748).mention} !", ephemeral=True)
        return
    
    latencia = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência: **{latencia}ms**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)
    


load_dotenv()
TOKEN = os.getenv("TOKEN")

async def main():
    await bot.start(TOKEN)  

asyncio.run(main())