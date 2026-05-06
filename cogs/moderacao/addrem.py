import time
import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio

class AddRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.command(name="addrole", description="Adiciona um cargo a um usuário")
    @app_commands.describe(
        usuario="Usuário para adicionar o cargo",
        cargo="Cargo a ser adicionado"
    )
    async def addrole(self, interaction: discord.Interaction, usuario: discord.Member, cargo: discord.Role):
        try:
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Você não tem permissão para gerenciar cargos.", ephemeral=True)
                return
            
            if cargo.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Não posso adicionar este cargo (posição muito alta).", ephemeral=True)
                return
            
            if cargo in usuario.roles:
                await interaction.response.send_message(f"❌ {usuario.mention} já possui o cargo {cargo.mention}.", ephemeral=True)
                return
            
            await usuario.add_roles(cargo)
            
            embed = discord.Embed(
                title="✅ Cargo Adicionado",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Usuário", value=usuario.mention, inline=True)
            embed.add_field(name="Cargo", value=cargo.mention, inline=True)
            embed.add_field(name="Adicionado por", value=interaction.user.mention, inline=True)
            embed.set_footer(text=f"ID: {usuario.id}")
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não tenho permissão para adicionar este cargo.", ephemeral=True)
        except Exception as e:
            print(f"Erro no comando addrole: {e}")
            await interaction.response.send_message("❌ Ocorreu um erro ao executar o comando.", ephemeral=True)
            
    @app_commands.command(name="addrole-all", description="Adiciona um cargo a todos usuários.")
    @app_commands.describe(cargo="Cargo a ser adicionado")
    async def addrole_all(self, interaction: discord.Interaction, cargo: discord.Role):
        try:
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Você não tem permissão para gerenciar cargos.", ephemeral=True)
                return
            
            if cargo.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Não posso adicionar este cargo (posição muito alta).", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            cont = 0
            members = [member for member in interaction.guild.members if not member.bot]
            
            for member in members:
                if cargo not in member.roles:
                    try:
                        await member.add_roles(cargo)
                        cont += 1
                    except discord.Forbidden:
                        continue
            
            embed = discord.Embed(
                title="✅ Cargo Adicionado a Todos",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Cargo", value=cargo.mention, inline=True)
            embed.add_field(name="Adicionado por", value=interaction.user.mention, inline=True)
            embed.add_field(name="Quantidade de cargos adicionados", value=f"{cont}/{len(members)} usuários", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Erro no comando addrole-all: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao executar o comando.", ephemeral=True)
    
    @app_commands.command(name="removerole", description="Remove um cargo de um usuário")
    @app_commands.describe(
        usuario="Usuário para remover o cargo",
        cargo="Cargo a ser removido"
    )
    async def removerole(self, interaction: discord.Interaction, usuario: discord.Member, cargo: discord.Role):
        try:
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Você não tem permissão para gerenciar cargos.", ephemeral=True)
                return
            
            if cargo in usuario.roles:
                await usuario.remove_roles(cargo)
                await interaction.response.send_message(f"✅ Cargo {cargo.mention} removido com sucesso de {usuario.mention}.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {usuario.mention} não possui o cargo {cargo.mention}.", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não tenho permissão para remover este cargo.", ephemeral=True)
        except Exception as e:
            print(f"Erro no comando removerole: {e}")
            await interaction.response.send_message("❌ Ocorreu um erro ao executar o comando.", ephemeral=True)
            
    @app_commands.command(name="removerole-all", description="Remove um cargo de todos usuários.")
    @app_commands.describe(cargo="Cargo a ser removido")
    async def removerole_all(self, interaction: discord.Interaction, cargo: discord.Role):
        try:
            if not interaction.user.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ Você não tem permissão para gerenciar cargos.", ephemeral=True)
                return
            
            if cargo.position >= interaction.guild.me.top_role.position:
                await interaction.response.send_message("❌ Não posso remover este cargo (posição muito alta).", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            cont = 0
            members = [member for member in interaction.guild.members if not member.bot]
            
            for member in members:
                if cargo in member.roles:
                    try:
                        await member.remove_roles(cargo)
                        cont += 1
                    except discord.Forbidden:
                        continue
            
            embed = discord.Embed(
                title="✅ Cargo Removido de Todos",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Cargo", value=cargo.mention, inline=True)
            embed.add_field(name="Removido por", value=interaction.user.mention, inline=True)
            embed.add_field(name="Quantidade de cargos removidos", value=f"{cont}/{len(members)} usuários", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Erro no comando removerole-all: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao executar o comando.", ephemeral=True)

              
async def setup(bot: commands.Bot):
    await bot.add_cog(AddRole(bot))