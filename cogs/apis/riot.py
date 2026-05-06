import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import os
from datetime import datetime
from urllib.parse import quote

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_REGION = os.getenv("RIOT_REGION", "br1")
RIOT_REGIONAL = "americas"

CANAL_COMANDOS = 1426205118293868748
CANAL_LOG = 1427479688544129064


class RiotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = RIOT_API_KEY
        self.region = RIOT_REGION
        self.base_url = f"https://{self.region}.api.riotgames.com"
        self.regional_url = f"https://{RIOT_REGIONAL}.api.riotgames.com"
        self.ddragon_version = None
        self.champion_data = {}

    async def _get(self, url: str, params: dict = None) -> dict | None:
        headers = {"X-Riot-Token": self.api_key}
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"❌ Riot API {resp.status}: {url}")
                    return None
        except aiohttp.ServerTimeoutError:
            print(f"❌ Riot API timeout: {url}")
            return None
        except Exception as e:
            print(f"❌ Riot API error: {e}")
            return None

    async def _parse_riot_id(self, nick: str) -> tuple[str, str] | None:
        """Extrai (gameName, tagLine) de 'Nome#TAG'. Retorna None se o formato for inválido."""
        if "#" not in nick:
            return None
        game_name, tag_line = nick.split("#", 1)
        return game_name.strip(), tag_line.strip()

    async def _get_puuid(self, game_name: str, tag_line: str) -> str | None:
        data = await self._get(
            f"{self.regional_url}/riot/account/v1/accounts/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
        )
        return data["puuid"] if data else None

    async def _get_summoner(self, nick: str) -> dict | None:
        """Resolve Riot ID (Nome#TAG) → PUUID → summoner data."""
        parsed = await self._parse_riot_id(nick)
        if parsed is None:
            return None
        game_name, tag_line = parsed
        puuid = await self._get_puuid(game_name, tag_line)
        if not puuid:
            return None
        data = await self._get(f"{self.base_url}/lol/summoner/v4/summoners/by-puuid/{puuid}")
        if data is not None:
            data.setdefault("name", game_name)
            data.setdefault("puuid", puuid)
        return data

    async def _get_tft_summoner(self, nick: str) -> dict | None:
        """Resolve Riot ID (Nome#TAG) → PUUID → TFT summoner data."""
        parsed = await self._parse_riot_id(nick)
        if parsed is None:
            return None
        game_name, tag_line = parsed
        puuid = await self._get_puuid(game_name, tag_line)
        if not puuid:
            return None
        data = await self._get(f"{self.base_url}/tft/summoner/v1/summoners/by-puuid/{puuid}")
        if data is not None:
            data.setdefault("name", game_name)
            data.setdefault("puuid", puuid)
        return data

    async def _get_champion_data(self) -> dict:
        if self.champion_data:
            return self.champion_data
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://ddragon.leagueoflegends.com/api/versions.json") as resp:
                    versions = await resp.json()
                    self.ddragon_version = versions[0]
                async with session.get(
                    f"https://ddragon.leagueoflegends.com/cdn/{self.ddragon_version}/data/pt_BR/champion.json"
                ) as resp:
                    data = await resp.json()
                    for champ in data["data"].values():
                        self.champion_data[int(champ["key"])] = champ["name"]
        except aiohttp.ServerTimeoutError:
            print("❌ Timeout ao carregar dados de campeões")
        except Exception as e:
            print(f"❌ Erro ao carregar dados de campeões: {e}")
        return self.champion_data

    # ─── Helpers visuais ─────────────────────────────────────────────────────

    _TIER_COLORS = {
        "IRON":         discord.Color.from_rgb(75,  80,  95),
        "BRONZE":       discord.Color.from_rgb(140, 90,  60),
        "SILVER":       discord.Color.from_rgb(158, 158, 158),
        "GOLD":         discord.Color.from_rgb(255, 200, 0),
        "PLATINUM":     discord.Color.from_rgb(48,  197, 176),
        "EMERALD":      discord.Color.from_rgb(0,   200, 64),
        "DIAMOND":      discord.Color.from_rgb(74,  144, 217),
        "MASTER":       discord.Color.from_rgb(155, 89,  182),
        "GRANDMASTER":  discord.Color.from_rgb(231, 76,  60),
        "CHALLENGER":   discord.Color.from_rgb(241, 196, 15),
    }
    _TIER_EMOJIS = {
        "IRON": "⚫", "BRONZE": "🟤", "SILVER": "⚪", "GOLD": "🟡",
        "PLATINUM": "🩵", "EMERALD": "🟢", "DIAMOND": "🔷",
        "MASTER": "🟣", "GRANDMASTER": "🔴", "CHALLENGER": "🏆",
    }

    def _cor_por_tier(self, tier: str | None) -> discord.Color:
        return self._TIER_COLORS.get(tier or "", discord.Color.blue())

    def _barra_wr(self, wins: int, losses: int, tamanho: int = 14) -> str:
        """Retorna uma barra ANSI colorida com o winrate."""
        total = wins + losses
        if total == 0:
            vazio = "[2;37m" + "░" * tamanho + "[0m"
            return f"{vazio}  [2;37mN/A[0m"

        wr = wins / total
        wr_pct = round(wr * 100)
        preenchido = round(wr * tamanho)
        vazio_n = tamanho - preenchido

        if wr >= 0.55:
            cor = "[1;32m"   # verde bold
        elif wr >= 0.50:
            cor = "[32m"     # verde
        elif wr >= 0.45:
            cor = "[33m"     # amarelo
        else:
            cor = "[1;31m"   # vermelho bold

        barra = (
            f"{cor}{'█' * preenchido}[0m"
            f"[2;37m{'░' * vazio_n}[0m"
            f"  {cor}{wr_pct}% WR[0m"
        )
        return barra

    def _campo_rank(self, entry: dict | None, label: str) -> tuple[str, str]:
        """Retorna (nome_campo, valor_campo) para um embed field de rank."""
        if not entry:
            emoji = "🎮"
            return f"{emoji} {label}", "*Unranked*"

        emoji = self._TIER_EMOJIS.get(entry["tier"], "🎮")
        wins, losses = entry["wins"], entry["losses"]
        barra = self._barra_wr(wins, losses)
        valor = (
            f"```ansi\n"
            f"{barra}\n"
            f"[0m{entry['tier']} {entry['rank']} · {entry['leaguePoints']} LP · {wins}W {losses}L"
            f"\n```"
        )
        return f"{emoji} {label}", valor

    def _canal_invalido(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return False
        return interaction.channel.id != CANAL_COMANDOS

    async def _resposta_canal_errado(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"❌ Ei, {interaction.user.mention}, use esse **comando** apenas em {self.bot.get_channel(CANAL_COMANDOS).mention}!",
            ephemeral=True,
        )

    # ─── League of Legends ───────────────────────────────────────────────────

    @app_commands.command(name="lol-perfil", description="Exibe o perfil completo de um invocador no LoL")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_perfil(self, interaction: discord.Interaction, nick: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        champion_data, summoner = await asyncio.gather(
            self._get_champion_data(),
            self._get_summoner(nick),
        )

        if not summoner:
            await interaction.followup.send(
                "❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).",
                ephemeral=True,
            )
            return

        sid = summoner.get("id", "")
        ranked, maestrias, total_score = await asyncio.gather(
            self._get(f"{self.base_url}/lol/league/v4/entries/by-summoner/{sid}"),
            self._get(
                f"{self.base_url}/lol/champion-mastery/v4/champion-masteries/by-summoner/{sid}/top",
                params={"count": 3},
            ),
            self._get(f"{self.base_url}/lol/champion-mastery/v4/scores/by-summoner/{sid}"),
        )

        solo = next((e for e in (ranked or []) if e["queueType"] == "RANKED_SOLO_5x5"), None)
        flex = next((e for e in (ranked or []) if e["queueType"] == "RANKED_FLEX_SR"), None)

        version = self.ddragon_version or "14.24.1"
        icon_id = summoner.get("profileIconId", 0)
        icon_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{icon_id}.png"

        revision = summoner.get("revisionDate")
        ultima_atividade = (
            f"\n⏱️ Última atividade: **{datetime.fromtimestamp(revision / 1000).strftime('%d/%m/%Y')}**"
            if revision else ""
        )

        embed = discord.Embed(
            title=f"🎮 {summoner.get('name', nick)}",
            description=(
                f"🌍 Servidor: **{self.region.upper()}** · "
                f"🏅 Nível **{summoner.get('summonerLevel', '?')}**"
                f"{ultima_atividade}"
            ),
            color=self._cor_por_tier(solo["tier"] if solo else None),
        )
        embed.set_thumbnail(url=icon_url)

        nome_solo, val_solo = self._campo_rank(solo, "Solo/Duo")
        nome_flex, val_flex = self._campo_rank(flex, "Flex")
        embed.add_field(name=nome_solo, value=val_solo, inline=True)
        embed.add_field(name=nome_flex, value=val_flex, inline=True)

        if maestrias:
            medalhas = ["🥇", "🥈", "🥉"]
            def _fmt_pts(n: int) -> str:
                return f"{n:,}".replace(",", ".")

            linhas = [
                f"{medalhas[i]} **{champion_data.get(m['championId'], str(m['championId']))}**"
                f" — Nv.{m['championLevel']} · {_fmt_pts(m['championPoints'])} pts"
                for i, m in enumerate(maestrias)
            ]
            score_linha = (
                f"\n🎯 Score total: **{_fmt_pts(total_score)}**"
                if isinstance(total_score, int) else ""
            )
            embed.add_field(name="⚔️ Top Maestrias", value="\n".join(linhas) + score_linha, inline=False)

        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-rank", description="Exibe o rank de um invocador no LoL")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_rank(self, interaction: discord.Interaction, nick: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        summoner = await self._get_summoner(nick)
        if not summoner:
            await interaction.followup.send("❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).", ephemeral=True)
            return

        ranked = await self._get(f"{self.base_url}/lol/league/v4/entries/by-summoner/{summoner['id']}")

        embed = discord.Embed(title=f"🏆 Rank de {summoner['name']}", color=discord.Color.gold())

        filas = {"RANKED_SOLO_5x5": "Solo/Duo", "RANKED_FLEX_SR": "Flex"}

        if ranked:
            for entrada in ranked:
                fila = filas.get(entrada["queueType"], entrada["queueType"])
                wins = entrada["wins"]
                losses = entrada["losses"]
                winrate = round(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                embed.add_field(
                    name=f"🎯 {fila}",
                    value=(
                        f"**{entrada['tier']} {entrada['rank']}** — {entrada['leaguePoints']} LP\n"
                        f"✅ {wins}V / ❌ {losses}D — {winrate}% WR"
                    ),
                    inline=False,
                )

        if not embed.fields:
            embed.description = "Sem dados de ranked (Unranked)"

        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-historico", description="Exibe o histórico de partidas de um invocador")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)", quantidade="Número de partidas (1-10)")
    async def lol_historico(self, interaction: discord.Interaction, nick: str, quantidade: int = 5):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        quantidade = max(1, min(quantidade, 10))
        await interaction.response.defer()

        summoner = await self._get_summoner(nick)
        if not summoner:
            await interaction.followup.send("❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).", ephemeral=True)
            return

        champion_data = await self._get_champion_data()

        match_ids = await self._get(
            f"{self.regional_url}/lol/match/v5/matches/by-puuid/{summoner['puuid']}/ids",
            params={"count": quantidade},
        )
        if not match_ids:
            await interaction.followup.send("❌ Histórico não encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 Histórico de {summoner['name']} (últimas {quantidade})",
            color=discord.Color.blue(),
        )

        for match_id in match_ids:
            match = await self._get(f"{self.regional_url}/lol/match/v5/matches/{match_id}")
            if not match:
                continue

            participant = next(
                (p for p in match["info"]["participants"] if p["puuid"] == summoner["puuid"]),
                None,
            )
            if not participant:
                continue

            champ_name = champion_data.get(participant["championId"], str(participant["championId"]))
            resultado = "✅ Vitória" if participant["win"] else "❌ Derrota"
            kills, deaths, assists = participant["kills"], participant["deaths"], participant["assists"]
            duracao = match["info"]["gameDuration"] // 60
            modo = match["info"]["gameMode"]

            embed.add_field(
                name=f"{resultado} — {champ_name} ({modo})",
                value=f"KDA: **{kills}/{deaths}/{assists}** • {duracao} min",
                inline=False,
            )

        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-maestria", description="Exibe as top 5 maestrias de campeões de um invocador")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_maestria(self, interaction: discord.Interaction, nick: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        summoner = await self._get_summoner(nick)
        if not summoner:
            await interaction.followup.send("❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).", ephemeral=True)
            return

        champion_data = await self._get_champion_data()

        maestrias = await self._get(
            f"{self.base_url}/lol/champion-mastery/v4/champion-masteries/by-summoner/{summoner['id']}/top",
            params={"count": 5},
        )
        if not maestrias:
            await interaction.followup.send("❌ Dados de maestria não encontrados.", ephemeral=True)
            return

        medalhas = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        embed = discord.Embed(
            title=f"⚔️ Top Maestrias de {summoner['name']}",
            color=discord.Color.purple(),
        )
        for i, m in enumerate(maestrias):
            champ_name = champion_data.get(m["championId"], str(m["championId"]))
            pontos = f"{m['championPoints']:,}".replace(",", ".")
            embed.add_field(
                name=f"{medalhas[i]} {champ_name}",
                value=f"Nível **{m['championLevel']}** — {pontos} pontos",
                inline=False,
            )

        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-rotacao", description="Campeões gratuitos desta semana no LoL")
    async def lol_rotacao(self, interaction: discord.Interaction):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        champion_data = await self._get_champion_data()
        rotacao = await self._get(f"{self.base_url}/lol/platform/v3/champion-rotations")

        if not rotacao:
            await interaction.followup.send("❌ Não foi possível obter a rotação.", ephemeral=True)
            return

        nomes = [champion_data.get(cid, str(cid)) for cid in rotacao.get("freeChampionIds", [])]
        nomes_novatos = [champion_data.get(cid, str(cid)) for cid in rotacao.get("freeChampionIdsForNewPlayers", [])]

        embed = discord.Embed(title="🎮 Rotação Semanal Gratuita", color=discord.Color.green())
        embed.add_field(name="🆓 Campeões Gratuitos", value=", ".join(nomes) or "N/A", inline=False)
        if nomes_novatos:
            embed.add_field(name="🌱 Para Novatos", value=", ".join(nomes_novatos), inline=False)
        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-aovivo", description="Exibe a partida atual de um invocador")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_aovivo(self, interaction: discord.Interaction, nick: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        summoner = await self._get_summoner(nick)
        if not summoner:
            await interaction.followup.send("❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).", ephemeral=True)
            return

        champion_data = await self._get_champion_data()
        live = await self._get(f"{self.base_url}/lol/spectator/v4/active-games/by-summoner/{summoner['id']}")

        if not live:
            await interaction.followup.send(f"❌ **{nick}** não está em partida no momento.", ephemeral=True)
            return

        duracao = live["gameLength"] // 60
        modo = live["gameMode"]
        azul = [p for p in live["participants"] if p["teamId"] == 100]
        vermelho = [p for p in live["participants"] if p["teamId"] == 200]

        def formatar_time(participantes):
            return "\n".join(
                f"• {p['summonerName']} — {champion_data.get(p['championId'], str(p['championId']))}"
                for p in participantes
            )

        embed = discord.Embed(
            title=f"🔴 AO VIVO — {nick}",
            description=f"**Modo:** {modo} • **Tempo:** {duracao} min",
            color=discord.Color.red(),
        )
        embed.add_field(name="🔵 Time Azul", value=formatar_time(azul), inline=True)
        embed.add_field(name="🔴 Time Vermelho", value=formatar_time(vermelho), inline=True)
        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-comparar", description="Compara o rank de dois invocadores")
    @app_commands.describe(nick1="Riot ID do 1º (ex: Faker#KR1)", nick2="Riot ID do 2º (ex: dededao#BR1)")
    async def lol_comparar(self, interaction: discord.Interaction, nick1: str, nick2: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        s1 = await self._get_summoner(nick1)
        s2 = await self._get_summoner(nick2)

        if not s1 or not s2:
            await interaction.followup.send("❌ Um ou ambos os invocadores não foram encontrados.", ephemeral=True)
            return

        r1 = await self._get(f"{self.base_url}/lol/league/v4/entries/by-summoner/{s1['id']}")
        r2 = await self._get(f"{self.base_url}/lol/league/v4/entries/by-summoner/{s2['id']}")

        def resumo(ranked, nome):
            if not ranked:
                return f"**{nome}**\nUnranked"
            solo = next((e for e in ranked if e["queueType"] == "RANKED_SOLO_5x5"), None)
            if not solo:
                return f"**{nome}**\nUnranked"
            wins, losses = solo["wins"], solo["losses"]
            wr = round(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            return f"**{nome}**\n{solo['tier']} {solo['rank']} — {solo['leaguePoints']} LP\n✅ {wins}V ❌ {losses}D — {wr}% WR"

        embed = discord.Embed(title="⚔️ Comparação de Rank", color=discord.Color.orange())
        embed.add_field(name="🔵 Jogador 1", value=resumo(r1, s1["name"]), inline=True)
        embed.add_field(name="🔴 Jogador 2", value=resumo(r2, s2["name"]), inline=True)
        embed.set_footer(text="Riot Games API • League of Legends")
        await interaction.followup.send(embed=embed)

    # ─── Teamfight Tactics ────────────────────────────────────────────────────

    @app_commands.command(name="tft-rank", description="Exibe o rank de um invocador no TFT")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def tft_rank(self, interaction: discord.Interaction, nick: str):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        await interaction.response.defer()

        summoner = await self._get_tft_summoner(nick)
        if not summoner:
            await interaction.followup.send(
                "❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).", ephemeral=True
            )
            return

        ranked = await self._get(f"{self.base_url}/tft/league/v1/entries/by-summoner/{summoner['id']}")

        embed = discord.Embed(title=f"🎲 TFT Rank de {summoner['name']}", color=discord.Color.teal())

        if ranked:
            for entrada in ranked:
                wins, losses = entrada["wins"], entrada["losses"]
                wr = round(wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                embed.add_field(
                    name="🏆 Ranked TFT",
                    value=(
                        f"**{entrada['tier']} {entrada['rank']}** — {entrada['leaguePoints']} LP\n"
                        f"✅ {wins}V / ❌ {losses}D — {wr}% WR"
                    ),
                    inline=False,
                )
        else:
            embed.description = "Sem dados de ranked (Unranked)"

        embed.set_footer(text="Riot Games API • Teamfight Tactics")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tft-historico", description="Exibe o histórico de partidas de TFT")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)", quantidade="Número de partidas (1-10)")
    async def tft_historico(self, interaction: discord.Interaction, nick: str, quantidade: int = 5):
        if self._canal_invalido(interaction):
            await self._resposta_canal_errado(interaction)
            return

        quantidade = max(1, min(quantidade, 10))
        await interaction.response.defer()

        summoner = await self._get_tft_summoner(nick)
        if not summoner:
            await interaction.followup.send(
                "❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).", ephemeral=True
            )
            return

        match_ids = await self._get(
            f"{self.regional_url}/tft/match/v1/matches/by-puuid/{summoner['puuid']}/ids",
            params={"count": quantidade},
        )
        if not match_ids:
            await interaction.followup.send("❌ Histórico não encontrado.", ephemeral=True)
            return

        emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

        embed = discord.Embed(
            title=f"📜 TFT Histórico de {summoner['name']} (últimas {quantidade})",
            color=discord.Color.teal(),
        )

        for match_id in match_ids:
            match = await self._get(f"{self.regional_url}/tft/match/v1/matches/{match_id}")
            if not match:
                continue

            participant = next(
                (p for p in match["info"]["participants"] if p["puuid"] == summoner["puuid"]),
                None,
            )
            if not participant:
                continue

            colocacao = participant["placement"]
            nivel = participant.get("level", "?")
            traits_ativos = [
                t["name"].split("_")[-1]
                for t in participant.get("traits", [])
                if t.get("tier_current", 0) > 0
            ][:3]
            traits_str = ", ".join(traits_ativos) if traits_ativos else "N/A"
            emoji = emojis[colocacao - 1] if 1 <= colocacao <= 8 else "💀"

            embed.add_field(
                name=f"{emoji} {colocacao}º lugar — Nível {nivel}",
                value=f"Traits ativos: {traits_str}",
                inline=False,
            )

        embed.set_footer(text="Riot Games API • Teamfight Tactics")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RiotCog(bot))
