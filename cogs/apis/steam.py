import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
from datetime import datetime

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
CANAL_COMANDOS = 1426205118293868748
STEAM_BASE = "http://api.steampowered.com"
STORE_BASE = "https://store.steampowered.com/api"

ESTADOS_PERSONA = {
    0: "⚫ Offline",
    1: "🟢 Online",
    2: "🟡 Ocupado",
    3: "🟡 Ausente",
    4: "🟡 Sonolento",
    5: "🟡 Querendo Trocar",
    6: "🟡 Querendo Jogar",
}


class SteamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = STEAM_API_KEY

    async def _get(self, url: str, params: dict = None) -> dict | None:
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"❌ Steam API {resp.status}: {url}")
                    return None
        except aiohttp.ServerTimeoutError:
            print(f"❌ Steam API timeout: {url}")
            return None
        except Exception as e:
            print(f"❌ Steam API error: {e}")
            return None

    def _canal_invalido(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return False
        return interaction.channel.id != CANAL_COMANDOS

    async def _resposta_canal_errado(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(CANAL_COMANDOS).mention}!",
            ephemeral=True,
        )

    @app_commands.command(name="steam-perfil", description="Exibe o perfil público de um usuário da Steam")
    @app_commands.describe(steamid="SteamID64 do usuário (número de 17 dígitos)")
    async def steam_perfil(self, interaction: discord.Interaction, steamid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STEAM_BASE}/ISteamUser/GetPlayerSummaries/v0002/",
            params={"key": self.api_key, "steamids": steamid},
        )

        if not data or not data["response"]["players"]:
            await interaction.followup.send(
                "❌ Perfil não encontrado. Verifique o SteamID64.", ephemeral=True
            )
            return

        player = data["response"]["players"][0]
        estado = ESTADOS_PERSONA.get(player.get("personastate", 0), "⚫ Offline")

        embed = discord.Embed(
            title=f"🎮 {player['personaname']}",
            url=player.get("profileurl", ""),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=player.get("avatarfull", ""))
        embed.add_field(name="📡 Status", value=estado, inline=True)

        if player.get("loccountrycode"):
            code = player["loccountrycode"].lower()
            embed.add_field(name="🌍 País", value=f":flag_{code}: {player['loccountrycode']}", inline=True)

        if player.get("timecreated"):
            criado = datetime.utcfromtimestamp(player["timecreated"]).strftime("%d/%m/%Y")
            embed.add_field(name="📅 Conta Criada", value=criado, inline=True)

        if player.get("gameextrainfo"):
            embed.add_field(name="🕹️ Jogando Agora", value=player["gameextrainfo"], inline=False)

        embed.set_footer(text=f"SteamID64: {steamid}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="steam-biblioteca", description="Exibe a biblioteca de jogos de um usuário na Steam")
    @app_commands.describe(steamid="SteamID64 do usuário")
    async def steam_biblioteca(self, interaction: discord.Interaction, steamid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STEAM_BASE}/IPlayerService/GetOwnedGames/v0001/",
            params={"key": self.api_key, "steamid": steamid, "include_appinfo": 1, "format": "json"},
        )

        if not data or not data["response"].get("games"):
            await interaction.followup.send(
                "❌ Biblioteca não encontrada. O perfil pode ser privado ou o SteamID64 inválido.",
                ephemeral=True,
            )
            return

        jogos = data["response"]["games"]
        total = len(jogos)
        total_horas = sum(j.get("playtime_forever", 0) for j in jogos) // 60
        mais_jogados = sorted(jogos, key=lambda x: x.get("playtime_forever", 0), reverse=True)[:5]

        embed = discord.Embed(title="📚 Biblioteca Steam", color=discord.Color.blue())
        embed.add_field(name="🎮 Total de Jogos", value=str(total), inline=True)
        embed.add_field(
            name="⏱️ Horas Totais", value=f"{total_horas:,}h".replace(",", "."), inline=True
        )

        top_str = "\n".join(
            f"• **{j['name']}** — {j.get('playtime_forever', 0) // 60}h"
            for j in mais_jogados
        )
        embed.add_field(name="🏆 Mais Jogados", value=top_str or "N/A", inline=False)
        embed.set_footer(text=f"SteamID64: {steamid}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="steam-recentes", description="Exibe os jogos jogados nas últimas 2 semanas")
    @app_commands.describe(steamid="SteamID64 do usuário")
    async def steam_recentes(self, interaction: discord.Interaction, steamid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STEAM_BASE}/IPlayerService/GetRecentlyPlayedGames/v0001/",
            params={"key": self.api_key, "steamid": steamid, "format": "json"},
        )

        if not data or not data["response"].get("games"):
            await interaction.followup.send(
                "❌ Nenhum jogo recente encontrado. O perfil pode ser privado.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🕹️ Jogos Recentes (últimas 2 semanas)", color=discord.Color.green()
        )
        for jogo in data["response"]["games"][:10]:
            horas_rec = jogo.get("playtime_2weeks", 0) // 60
            mins_rec = (jogo.get("playtime_2weeks", 0) % 60)
            horas_tot = jogo.get("playtime_forever", 0) // 60
            tempo_rec = f"{horas_rec}h {mins_rec}m" if horas_rec > 0 else f"{mins_rec}m"
            embed.add_field(
                name=jogo["name"],
                value=f"⏱️ Recente: **{tempo_rec}** | Total: {horas_tot}h",
                inline=False,
            )

        embed.set_footer(text=f"SteamID64: {steamid}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="steam-conquistas", description="Conquistas de um usuário em um jogo específico")
    @app_commands.describe(steamid="SteamID64 do usuário", appid="AppID do jogo (ex: 730 para CS2)")
    async def steam_conquistas(self, interaction: discord.Interaction, steamid: str, appid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STEAM_BASE}/ISteamUserStats/GetPlayerAchievements/v0001/",
            params={"key": self.api_key, "steamid": steamid, "appid": appid, "l": "portuguese"},
        )

        if not data or data.get("playerstats", {}).get("error"):
            await interaction.followup.send(
                "❌ Conquistas não encontradas. Verifique o SteamID64, AppID e se o perfil é público.",
                ephemeral=True,
            )
            return

        stats = data["playerstats"]
        achievements = stats.get("achievements", [])

        if not achievements:
            await interaction.followup.send("❌ Nenhuma conquista encontrada para esse jogo.", ephemeral=True)
            return

        total = len(achievements)
        desbloqueadas = sum(1 for a in achievements if a.get("achieved") == 1)
        percentual = round(desbloqueadas / total * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"🏆 Conquistas — {stats.get('gameName', 'Jogo')}",
            description=f"✅ **{desbloqueadas}/{total}** conquistas desbloqueadas ({percentual}%)",
            color=discord.Color.gold(),
        )

        recentes = sorted(
            [a for a in achievements if a.get("achieved") == 1 and a.get("unlocktime")],
            key=lambda x: x["unlocktime"],
            reverse=True,
        )[:5]

        if recentes:
            recentes_str = "\n".join(
                f"• {a.get('name', a['apiname'])} — {datetime.utcfromtimestamp(a['unlocktime']).strftime('%d/%m/%Y')}"
                for a in recentes
            )
            embed.add_field(name="🕐 Últimas Desbloqueadas", value=recentes_str, inline=False)

        embed.set_footer(text=f"SteamID64: {steamid} | AppID: {appid}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="steam-amigos", description="Lista os amigos online de um usuário na Steam")
    @app_commands.describe(steamid="SteamID64 do usuário")
    async def steam_amigos(self, interaction: discord.Interaction, steamid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STEAM_BASE}/ISteamUser/GetFriendList/v0001/",
            params={"key": self.api_key, "steamid": steamid, "relationship": "friend"},
        )

        if not data or not data.get("friendslist"):
            await interaction.followup.send(
                "❌ Lista de amigos não encontrada. O perfil pode ser privado.", ephemeral=True
            )
            return

        amigos = data["friendslist"]["friends"]
        total = len(amigos)

        if not amigos:
            await interaction.followup.send("Nenhum amigo encontrado.", ephemeral=True)
            return

        ids = ",".join(a["steamid"] for a in amigos[:20])
        perfis_data = await self._get(
            f"{STEAM_BASE}/ISteamUser/GetPlayerSummaries/v0002/",
            params={"key": self.api_key, "steamids": ids},
        )

        embed = discord.Embed(
            title="👥 Lista de Amigos Steam",
            description=f"Total: **{total}** amigos (exibindo até 20)",
            color=discord.Color.blue(),
        )

        if perfis_data:
            jogadores = perfis_data["response"]["players"]
            online = [p for p in jogadores if p.get("personastate", 0) != 0]
            offline = [p for p in jogadores if p.get("personastate", 0) == 0]

            if online:
                online_str = "\n".join(f"• 🟢 {p['personaname']}" for p in online[:10])
                embed.add_field(name=f"Online ({len(online)})", value=online_str, inline=False)
            if offline:
                offline_str = "\n".join(f"• ⚫ {p['personaname']}" for p in offline[:10])
                embed.add_field(name=f"Offline ({len(offline)})", value=offline_str, inline=False)

        embed.set_footer(text=f"SteamID64: {steamid}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="steam-bans", description="Verifica o histórico de bans de um usuário na Steam")
    @app_commands.describe(steamid="SteamID64 do usuário")
    async def steam_bans(self, interaction: discord.Interaction, steamid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STEAM_BASE}/ISteamUser/GetPlayerBans/v1/",
            params={"key": self.api_key, "steamids": steamid},
        )

        if not data or not data.get("players"):
            await interaction.followup.send("❌ Usuário não encontrado.", ephemeral=True)
            return

        player = data["players"][0]
        banido = player["VACBanned"] or player["NumberOfGameBans"] > 0

        embed = discord.Embed(
            title="🚫 Histórico de Bans Steam",
            color=discord.Color.red() if banido else discord.Color.green(),
        )
        embed.add_field(
            name="🛡️ VAC Ban", value="❌ SIM" if player["VACBanned"] else "✅ Limpo", inline=True
        )
        embed.add_field(name="🎮 Game Bans", value=str(player["NumberOfGameBans"]), inline=True)
        embed.add_field(
            name="🏘️ Comunidade",
            value="❌ SIM" if player["CommunityBanned"] else "✅ Limpo",
            inline=True,
        )
        if player["VACBanned"] and player.get("DaysSinceLastBan"):
            embed.add_field(name="📅 Último Ban", value=f"Há {player['DaysSinceLastBan']} dias", inline=True)

        embed.set_footer(text=f"SteamID64: {steamid}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="steam-jogo", description="Exibe informações de um jogo na Steam")
    @app_commands.describe(appid="AppID do jogo (ex: 730 para CS2, 570 para Dota 2)")
    async def steam_jogo(self, interaction: discord.Interaction, appid: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        data = await self._get(
            f"{STORE_BASE}/appdetails", params={"appids": appid, "l": "portuguese"}
        )

        if not data or not data.get(appid, {}).get("success"):
            await interaction.followup.send("❌ Jogo não encontrado. Verifique o AppID.", ephemeral=True)
            return

        jogo = data[appid]["data"]
        preco_info = jogo.get("price_overview", {})
        preco_str = preco_info.get("final_formatted", "Gratuito") if preco_info else "Gratuito"
        generos = ", ".join(g["description"] for g in jogo.get("genres", [])[:4]) or "N/A"
        devs = ", ".join(jogo.get("developers", [])[:2]) or "N/A"
        descricao = jogo.get("short_description", "")[:300]

        embed = discord.Embed(
            title=jogo["name"],
            description=descricao,
            url=f"https://store.steampowered.com/app/{appid}",
            color=discord.Color.blue(),
        )
        embed.set_image(url=jogo.get("header_image", ""))
        embed.add_field(name="💰 Preço", value=preco_str, inline=True)
        embed.add_field(name="🎮 Gêneros", value=generos, inline=True)
        embed.add_field(name="🏢 Desenvolvedor", value=devs, inline=True)

        if jogo.get("metacritic"):
            embed.add_field(name="🎯 Metacritic", value=str(jogo["metacritic"]["score"]), inline=True)

        if jogo.get("recommendations"):
            total_rec = jogo["recommendations"].get("total", 0)
            embed.add_field(name="👍 Recomendações", value=f"{total_rec:,}".replace(",", "."), inline=True)

        embed.set_footer(text=f"AppID: {appid} • Steam Store")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SteamCog(bot))
