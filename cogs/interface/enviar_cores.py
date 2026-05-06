import discord
from discord.ext import commands

CARGOS_GRATUITOS = [
    1428066709356548217,
    1428066760141045771,
    1428066489419825325,
    1428066484889849896,
    1428066757322473588
]
CORES_PREMIUM = [
    1428400034952515696,
    1428400132272951358,
    1428399718945390764,
    1428399137057013783
]

class CoresDropdown(discord.ui.Select):
    def __init__(self):
        options = []
        super().__init__(
            placeholder="Selecione sua cor gratuita...",
            options=options,
            custom_id="cores_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        cargo_id = int(self.values[0])
        cargo = interaction.guild.get_role(cargo_id)
        if cargo:
            for c_id in CARGOS_GRATUITOS:
                c = interaction.guild.get_role(c_id)
                if c and c in interaction.user.roles:
                    await interaction.user.remove_roles(c)
            
            await interaction.user.add_roles(cargo)
            await interaction.response.send_message(
                f"✅ Você recebeu o cargo **{cargo.name}**!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Não consegui encontrar o cargo selecionado.",
                ephemeral=True
            )

class CoresView(discord.ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.select = CoresDropdown()
        self.select.options = options
        self.add_item(self.select)

class EnviarCores(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cores(self, channel):
        embed = discord.Embed(
            title="🎨 Cores Disponíveis",
            description="Visualize os **padrões** de cores **disponíveis**:",
            color=discord.Color.blurple()
        )

        cargos_nomes = []
        cores_premium = []
        options = []
        
        for cargo_id in CARGOS_GRATUITOS:
            cargo = channel.guild.get_role(cargo_id)
            if cargo:
                cargos_nomes.append(f"• {cargo.mention}")
                options.append(discord.SelectOption(label=cargo.name, value=str(cargo.id)))  # Mudei para .name
                
        for cargo_id in CORES_PREMIUM:
            cargo = channel.guild.get_role(cargo_id)
            if cargo:
                cores_premium.append(f"• {cargo.mention}")

        if not cargos_nomes:
            await channel.send("❌ Não foi possível encontrar os cargos de cores.")
            return

        embed.add_field(name="Cores Gratuitas:", value="\n".join(cargos_nomes), inline=False)
        embed.add_field(name="Cores Premium:", value="\n".join(cores_premium), inline=True)    
        embed.set_footer(text="© 2025 ALCATEIA DO FENRIR. Todos os direitos reservados.")

        view = CoresView(options)
        
        await channel.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(EnviarCores(bot))