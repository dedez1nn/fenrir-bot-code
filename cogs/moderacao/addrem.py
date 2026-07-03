import time
import discord
from discord.ext import commands
import random
import asyncio

class AddRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="addrole")
    @commands.has_permissions(manage_roles=True)
    async def addrole(self, ctx: commands.Context, usuario: discord.Member, cargo: discord.Role):
        try:
            if cargo.position >= ctx.guild.me.top_role.position:
                await ctx.send("❌ Não posso adicionar este cargo (posição muito alta).")
                return

            if cargo in usuario.roles:
                await ctx.send(f"❌ {usuario.mention} já possui o cargo {cargo.mention}.")
                return

            await usuario.add_roles(cargo)

            embed = discord.Embed(
                title="✅ Cargo Adicionado",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Usuário", value=usuario.mention, inline=True)
            embed.add_field(name="Cargo", value=cargo.mention, inline=True)
            embed.add_field(name="Adicionado por", value=ctx.author.mention, inline=True)
            embed.set_footer(text=f"ID: {usuario.id}")

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("❌ Não tenho permissão para adicionar este cargo.")
        except Exception as e:
            print(f"Erro no comando addrole: {e}")
            await ctx.send("❌ Ocorreu um erro ao executar o comando.")

    @commands.command(name="addrole-all")
    @commands.has_permissions(manage_roles=True)
    async def addrole_all(self, ctx: commands.Context, cargo: discord.Role):
        try:
            if cargo.position >= ctx.guild.me.top_role.position:
                await ctx.send("❌ Não posso adicionar este cargo (posição muito alta).")
                return

            cont = 0
            members = [member for member in ctx.guild.members if not member.bot]

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
            embed.add_field(name="Adicionado por", value=ctx.author.mention, inline=True)
            embed.add_field(name="Quantidade de cargos adicionados", value=f"{cont}/{len(members)} usuários", inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Erro no comando addrole-all: {e}")
            await ctx.send("❌ Ocorreu um erro ao executar o comando.")

    @commands.command(name="removerole")
    @commands.has_permissions(manage_roles=True)
    async def removerole(self, ctx: commands.Context, usuario: discord.Member, cargo: discord.Role):
        try:
            if cargo in usuario.roles:
                await usuario.remove_roles(cargo)
                await ctx.send(f"✅ Cargo {cargo.mention} removido com sucesso de {usuario.mention}.")
            else:
                await ctx.send(f"❌ {usuario.mention} não possui o cargo {cargo.mention}.")

        except discord.Forbidden:
            await ctx.send("❌ Não tenho permissão para remover este cargo.")
        except Exception as e:
            print(f"Erro no comando removerole: {e}")
            await ctx.send("❌ Ocorreu um erro ao executar o comando.")

    @commands.command(name="removerole-all")
    @commands.has_permissions(manage_roles=True)
    async def removerole_all(self, ctx: commands.Context, cargo: discord.Role):
        try:
            if cargo.position >= ctx.guild.me.top_role.position:
                await ctx.send("❌ Não posso remover este cargo (posição muito alta).")
                return

            cont = 0
            members = [member for member in ctx.guild.members if not member.bot]

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
            embed.add_field(name="Removido por", value=ctx.author.mention, inline=True)
            embed.add_field(name="Quantidade de cargos removidos", value=f"{cont}/{len(members)} usuários", inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            print(f"Erro no comando removerole-all: {e}")
            await ctx.send("❌ Ocorreu um erro ao executar o comando.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AddRole(bot))