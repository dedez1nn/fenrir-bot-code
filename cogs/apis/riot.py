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


E = ""  # ESC para ANSI nos code blocks do Discord

_QUEUE_NAMES: dict[int, str] = {
    420: "Solo/Duo",
    440: "Flex",
    400: "Normal (Rascunho)",
    430: "Normal (Cego)",
    450: "ARAM",
    900: "URF",
    76:  "URF",
    325: "ARURF",
    1020: "Um por Todos",
    1900: "URF",
    830: "Co-op vs IA",
    840: "Co-op vs IA",
    850: "Co-op vs IA",
}


class RiotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = RIOT_API_KEY
        self.region = RIOT_REGION
        self.base_url = f"https://{self.region}.api.riotgames.com"
        self.regional_url = f"https://{RIOT_REGIONAL}.api.riotgames.com"
        self.ddragon_version = None
        self.champion_data: dict[int, str] = {}
        self.champion_key_data: dict[int, str] = {}

    # ─── HTTP ────────────────────────────────────────────────────────────────

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
        except Exception as ex:
            print(f"❌ Riot API error: {ex}")
            return None

    # ─── Resolução de Riot ID ────────────────────────────────────────────────

    async def _parse_riot_id(self, nick: str) -> tuple[str, str] | None:
        if "#" not in nick:
            return None
        game_name, tag_line = nick.split("#", 1)
        return game_name.strip(), tag_line.strip()

    async def _get_puuid(self, game_name: str, tag_line: str) -> str | None:
        data = await self._get(
            f"{self.regional_url}/riot/account/v1/accounts/by-riot-id"
            f"/{quote(game_name)}/{quote(tag_line)}"
        )
        return data["puuid"] if data else None

    async def _get_summoner(self, nick: str) -> dict | None:
        parsed = await self._parse_riot_id(nick)
        if not parsed:
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
        parsed = await self._parse_riot_id(nick)
        if not parsed:
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
                async with session.get(
                    "https://ddragon.leagueoflegends.com/api/versions.json"
                ) as resp:
                    versions = await resp.json()
                    self.ddragon_version = versions[0]
                async with session.get(
                    f"https://ddragon.leagueoflegends.com/cdn"
                    f"/{self.ddragon_version}/data/pt_BR/champion.json"
                ) as resp:
                    data = await resp.json()
                    for champ in data["data"].values():
                        cid = int(champ["key"])
                        self.champion_data[cid] = champ["name"]
                        self.champion_key_data[cid] = champ["id"]
        except aiohttp.ServerTimeoutError:
            print("❌ Timeout ao carregar dados de campeões")
        except Exception as ex:
            print(f"❌ Erro ao carregar dados de campeões: {ex}")
        return self.champion_data

    # ─── Helpers visuais ─────────────────────────────────────────────────────

    _TIER_PT = {
        "IRON": "Ferro", "BRONZE": "Bronze", "SILVER": "Prata",
        "GOLD": "Ouro", "PLATINUM": "Platina", "EMERALD": "Esmeralda",
        "DIAMOND": "Diamante", "MASTER": "Mestre",
        "GRANDMASTER": "Grão-Mestre", "CHALLENGER": "Desafiante",
    }
    _TIER_COLORS = {
        "IRON":        discord.Color.from_rgb(75,  80,  95),
        "BRONZE":      discord.Color.from_rgb(140, 90,  60),
        "SILVER":      discord.Color.from_rgb(158, 158, 158),
        "GOLD":        discord.Color.from_rgb(205, 160, 0),
        "PLATINUM":    discord.Color.from_rgb(48,  197, 176),
        "EMERALD":     discord.Color.from_rgb(0,   200, 64),
        "DIAMOND":     discord.Color.from_rgb(74,  144, 217),
        "MASTER":      discord.Color.from_rgb(155, 89,  182),
        "GRANDMASTER": discord.Color.from_rgb(231, 76,  60),
        "CHALLENGER":  discord.Color.from_rgb(241, 196, 15),
    }
    _TIER_EMOJIS = {
        "IRON": "⚫", "BRONZE": "🟤", "SILVER": "⚪", "GOLD": "🟡",
        "PLATINUM": "🩵", "EMERALD": "🟢", "DIAMOND": "🔷",
        "MASTER": "🟣", "GRANDMASTER": "🔴", "CHALLENGER": "🏆",
    }

    def _cor_por_tier(self, tier: str | None) -> discord.Color:
        return self._TIER_COLORS.get(tier or "", discord.Color.from_rgb(88, 101, 242))

    @staticmethod
    def _fmt_pts(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    def _barra_wr(self, wins: int, losses: int, tamanho: int = 16) -> str:
        total = wins + losses
        rst = f"{E}[0m"
        vazio_cor = f"{E}[90m"   # cinza visível no tema escuro

        if total == 0:
            return f"{vazio_cor}{'░' * tamanho}{rst}  {vazio_cor}N/A{rst}"

        wr = wins / total
        wr_pct = round(wr * 100)
        preenchido = round(wr * tamanho)
        vazio_n = tamanho - preenchido

        if wr >= 0.56:
            cor = f"{E}[1;92m"   # verde claro bold
        elif wr >= 0.50:
            cor = f"{E}[92m"     # verde claro
        elif wr >= 0.45:
            cor = f"{E}[1;93m"   # amarelo claro bold
        else:
            cor = f"{E}[1;91m"   # vermelho claro bold

        return (
            f"{cor}{'█' * preenchido}{rst}"
            f"{vazio_cor}{'░' * vazio_n}{rst}"
            f"  {cor}{wr_pct}% WR{rst}"
        )

    def _campo_rank(self, entry: dict | None, label: str) -> tuple[str, str]:
        if not entry:
            emoji = "➖"
            return (
                f"{emoji} {label}",
                f"```ansi\n{E}[90m{'░' * 16}{E}[0m  {E}[90mSem classificação{E}[0m\n```",
            )
        emoji = self._TIER_EMOJIS.get(entry["tier"], "🎮")
        tier_pt = self._TIER_PT.get(entry["tier"], entry["tier"])
        divisao = entry.get("rank", "")
        rank_str = f"{tier_pt} {divisao}".strip()
        wins, losses = entry["wins"], entry["losses"]
        barra = self._barra_wr(wins, losses)
        valor = (
            f"```ansi\n"
            f"{barra}\n"
            f"{E}[0m{rank_str} · {entry['leaguePoints']} LP\n"
            f"{E}[90m{wins}V  {losses}D{E}[0m"
            f"\n```"
        )
        return f"{emoji} {label}", valor

    async def _canal_invalido(self, interaction: discord.Interaction) -> bool:
        return await self.bot.guard_channel(interaction)

    # ─── League of Legends ───────────────────────────────────────────────────

    @app_commands.command(name="lol-perfil", description="Exibe o perfil completo de um invocador no LoL")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_perfil(self, interaction: discord.Interaction, nick: str):
        if await self._canal_invalido(interaction):
            return
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

        puuid = summoner["puuid"]
        ranked, maestrias, total_score = await asyncio.gather(
            self._get(f"{self.base_url}/lol/league/v4/entries/by-puuid/{puuid}"),
            self._get(
                f"{self.base_url}/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top",
                params={"count": 3},
            ),
            self._get(f"{self.base_url}/lol/champion-mastery/v4/scores/by-puuid/{puuid}"),
        )

        solo = next((e for e in (ranked or []) if e["queueType"] == "RANKED_SOLO_5x5"), None)
        flex = next((e for e in (ranked or []) if e["queueType"] == "RANKED_FLEX_SR"), None)

        version = self.ddragon_version or "14.24.1"
        icon_url = (
            f"https://ddragon.leagueoflegends.com/cdn/{version}"
            f"/img/profileicon/{summoner.get('profileIconId', 0)}.png"
        )

        revision = summoner.get("revisionDate")
        atividade = (
            f"\n⏱️ Visto por último em **{datetime.fromtimestamp(revision / 1000).strftime('%d/%m/%Y')}**"
            if revision else ""
        )

        tier_display = ""
        if solo:
            tier_pt = self._TIER_PT.get(solo["tier"], solo["tier"])
            divisao = solo.get("rank", "")
            tier_display = f" — {tier_pt} {divisao}".strip()

        embed = discord.Embed(
            title=f"🎮  {summoner.get('name', nick)}{tier_display}",
            description=(
                f"🌍 **{self.region.upper()}**  ·  "
                f"🏅 Nível **{summoner.get('summonerLevel', '?')}**"
                f"{atividade}"
            ),
            color=self._cor_por_tier(solo["tier"] if solo else None),
        )
        embed.set_thumbnail(url=icon_url)

        n_solo, v_solo = self._campo_rank(solo, "Solo / Duo")
        n_flex, v_flex = self._campo_rank(flex, "Flex 5×5")
        embed.add_field(name=n_solo, value=v_solo, inline=True)
        embed.add_field(name=n_flex, value=v_flex, inline=True)

        if maestrias:
            medalhas = ["🥇", "🥈", "🥉"]
            linhas = [
                f"{medalhas[i]}  **{champion_data.get(m['championId'], str(m['championId']))}**"
                f"  —  Nv. {m['championLevel']}  ·  {self._fmt_pts(m['championPoints'])} pts"
                for i, m in enumerate(maestrias)
            ]
            score_linha = (
                f"\n\n🎯  Score total: **{self._fmt_pts(total_score)}**"
                if isinstance(total_score, int) else ""
            )
            embed.add_field(
                name="⚔️  Top Maestrias",
                value="\n".join(linhas) + score_linha,
                inline=False,
            )

        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-rank", description="Exibe o rank de um invocador no LoL")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_rank(self, interaction: discord.Interaction, nick: str):
        if await self._canal_invalido(interaction):
            return
            return

        await interaction.response.defer()

        summoner = await self._get_summoner(nick)
        if not summoner:
            await interaction.followup.send(
                "❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).",
                ephemeral=True,
            )
            return

        ranked = await self._get(f"{self.base_url}/lol/league/v4/entries/by-puuid/{summoner['puuid']}")
        solo = next((e for e in (ranked or []) if e["queueType"] == "RANKED_SOLO_5x5"), None)
        flex = next((e for e in (ranked or []) if e["queueType"] == "RANKED_FLEX_SR"), None)

        version = self.ddragon_version or "14.24.1"
        icon_url = (
            f"https://ddragon.leagueoflegends.com/cdn/{version}"
            f"/img/profileicon/{summoner.get('profileIconId', 0)}.png"
        )

        embed = discord.Embed(
            title=f"🏆  Rank  —  {summoner.get('name', nick)}",
            color=self._cor_por_tier(solo["tier"] if solo else None),
        )
        embed.set_thumbnail(url=icon_url)

        n_solo, v_solo = self._campo_rank(solo, "Solo / Duo")
        n_flex, v_flex = self._campo_rank(flex, "Flex 5×5")
        embed.add_field(name=n_solo, value=v_solo, inline=True)
        embed.add_field(name=n_flex, value=v_flex, inline=True)

        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-historico", description="Exibe o histórico de partidas de um invocador")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)", quantidade="Número de partidas (1-10)")
    async def lol_historico(self, interaction: discord.Interaction, nick: str, quantidade: int = 5):
        if await self._canal_invalido(interaction):
            return
            return

        quantidade = max(1, min(quantidade, 10))
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

        match_ids = await self._get(
            f"{self.regional_url}/lol/match/v5/matches/by-puuid/{summoner['puuid']}/ids",
            params={"count": quantidade},
        )
        if not match_ids:
            await interaction.followup.send("❌ Histórico não encontrado.", ephemeral=True)
            return

        matches = await asyncio.gather(
            *[self._get(f"{self.regional_url}/lol/match/v5/matches/{mid}") for mid in match_ids]
        )

        embed = discord.Embed(
            title=f"📜  Histórico  —  {summoner.get('name', nick)}",
            color=discord.Color.from_rgb(88, 101, 242),
        )

        for match in matches:
            if not match:
                continue
            participant = next(
                (p for p in match["info"]["participants"] if p["puuid"] == summoner["puuid"]),
                None,
            )
            if not participant:
                continue

            champ_name = champion_data.get(participant["championId"], str(participant["championId"]))
            wins = participant["win"]
            resultado_emoji = "✅" if wins else "❌"
            resultado_str = "Vitória" if wins else "Derrota"

            k, d, a = participant["kills"], participant["deaths"], participant["assists"]
            kda_ratio = round((k + a) / max(1, d), 2)
            cs = participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0)
            nivel = participant.get("champLevel", "?")
            duracao_s = match["info"]["gameDuration"]
            mins, secs = duracao_s // 60, duracao_s % 60

            queue_id = match["info"].get("queueId", 0)
            modo = _QUEUE_NAMES.get(queue_id, match["info"].get("gameMode", "?"))

            embed.add_field(
                name=f"{resultado_emoji}  {resultado_str}  ·  {champ_name}  ·  {modo}  ·  {mins}m{secs:02d}s",
                value=(
                    f"⚔️  `{k}/{d}/{a}`  ({kda_ratio:.2f} KDA)"
                    f"  ·  🌾 **{cs}** CS"
                    f"  ·  Nv. **{nivel}**"
                ),
                inline=False,
            )

        if not embed.fields:
            embed.description = "Nenhuma partida encontrada."

        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-maestria", description="Exibe as top 5 maestrias de campeões de um invocador")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_maestria(self, interaction: discord.Interaction, nick: str):
        if await self._canal_invalido(interaction):
            return
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

        maestrias, total_score = await asyncio.gather(
            self._get(
                f"{self.base_url}/lol/champion-mastery/v4/champion-masteries/by-puuid/{summoner['puuid']}/top",
                params={"count": 5},
            ),
            self._get(f"{self.base_url}/lol/champion-mastery/v4/scores/by-puuid/{summoner['puuid']}"),
        )
        if not maestrias:
            await interaction.followup.send("❌ Dados de maestria não encontrados.", ephemeral=True)
            return

        medalhas = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        version = self.ddragon_version or "14.24.1"
        top_champ_key = self.champion_key_data.get(maestrias[0]["championId"], "")
        thumb_url = (
            f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{top_champ_key}.png"
            if top_champ_key else discord.Embed.Empty
        )

        score_str = (
            f"\n\n🎯  Score total: **{self._fmt_pts(total_score)}**"
            if isinstance(total_score, int) else ""
        )

        linhas = []
        for i, m in enumerate(maestrias):
            champ_name = champion_data.get(m["championId"], str(m["championId"]))
            pontos = self._fmt_pts(m["championPoints"])
            estrelas = "⭐" * min(m["championLevel"], 7)
            linhas.append(
                f"{medalhas[i]}  **{champ_name}**  {estrelas}\n"
                f"　　Nv. {m['championLevel']}  ·  {pontos} pts"
            )

        embed = discord.Embed(
            title=f"⚔️  Top Maestrias  —  {summoner.get('name', nick)}",
            description="\n\n".join(linhas) + score_str,
            color=discord.Color.from_rgb(155, 89, 182),
        )
        if top_champ_key:
            embed.set_thumbnail(url=thumb_url)

        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-rotacao", description="Campeões gratuitos desta semana no LoL")
    async def lol_rotacao(self, interaction: discord.Interaction):
        if await self._canal_invalido(interaction):
            return
            return

        await interaction.response.defer()

        champion_data, rotacao = await asyncio.gather(
            self._get_champion_data(),
            self._get(f"{self.base_url}/lol/platform/v3/champion-rotations"),
        )
        if not rotacao:
            await interaction.followup.send("❌ Não foi possível obter a rotação.", ephemeral=True)
            return

        nomes = [champion_data.get(cid, str(cid)) for cid in rotacao.get("freeChampionIds", [])]
        novatos = [champion_data.get(cid, str(cid)) for cid in rotacao.get("freeChampionIdsForNewPlayers", [])]

        def colunas(lista: list[str], n: int = 3) -> str:
            linhas = [lista[i:i+n] for i in range(0, len(lista), n)]
            return "\n".join("  ·  ".join(col) for col in linhas) or "N/A"

        embed = discord.Embed(
            title="🎮  Rotação Semanal Gratuita",
            color=discord.Color.from_rgb(0, 200, 64),
        )
        embed.add_field(name="🆓  Campeões Gratuitos", value=colunas(nomes), inline=False)
        if novatos:
            embed.add_field(name="🌱  Para Novatos", value=colunas(novatos), inline=False)
        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-aovivo", description="Exibe a partida atual de um invocador")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def lol_aovivo(self, interaction: discord.Interaction, nick: str):
        if await self._canal_invalido(interaction):
            return
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

        live = await self._get(
            f"{self.base_url}/lol/spectator/v5/active-games/by-summoner/{summoner['puuid']}"
        )
        if not live:
            await interaction.followup.send(
                f"❌ **{nick}** não está em partida no momento.", ephemeral=True
            )
            return

        mins = live["gameLength"] // 60
        secs = live["gameLength"] % 60
        queue_id = live.get("gameQueueConfigId", 0)
        modo = _QUEUE_NAMES.get(queue_id, live.get("gameMode", "?"))

        def formatar_time(participantes: list) -> str:
            linhas = []
            for p in participantes:
                name = p.get("riotId") or p.get("summonerName", "?")
                champ = champion_data.get(p["championId"], str(p["championId"]))
                linhas.append(f"**{champ}**  —  {name}")
            return "\n".join(linhas)

        azul = [p for p in live["participants"] if p["teamId"] == 100]
        vermelho = [p for p in live["participants"] if p["teamId"] == 200]

        embed = discord.Embed(
            title=f"🔴  AO VIVO  —  {nick}",
            description=f"**{modo}**  ·  `{mins}:{secs:02d}` em andamento",
            color=discord.Color.from_rgb(231, 76, 60),
        )
        embed.add_field(name="🔵  Time Azul", value=formatar_time(azul), inline=True)
        embed.add_field(name="🔴  Time Vermelho", value=formatar_time(vermelho), inline=True)
        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lol-comparar", description="Compara o rank de dois invocadores")
    @app_commands.describe(nick1="Riot ID do 1º (ex: Faker#KR1)", nick2="Riot ID do 2º (ex: dededao#BR1)")
    async def lol_comparar(self, interaction: discord.Interaction, nick1: str, nick2: str):
        if await self._canal_invalido(interaction):
            return
            return

        await interaction.response.defer()

        s1, s2 = await asyncio.gather(
            self._get_summoner(nick1),
            self._get_summoner(nick2),
        )
        if not s1 or not s2:
            await interaction.followup.send(
                "❌ Um ou ambos os invocadores não foram encontrados.", ephemeral=True
            )
            return

        r1, r2 = await asyncio.gather(
            self._get(f"{self.base_url}/lol/league/v4/entries/by-puuid/{s1['puuid']}"),
            self._get(f"{self.base_url}/lol/league/v4/entries/by-puuid/{s2['puuid']}"),
        )

        def solo_entry(ranked):
            return next((e for e in (ranked or []) if e["queueType"] == "RANKED_SOLO_5x5"), None)

        e1, e2 = solo_entry(r1), solo_entry(r2)
        color = self._cor_por_tier(e1["tier"] if e1 else (e2["tier"] if e2 else None))

        n1, v1 = self._campo_rank(e1, s1.get("name", nick1))
        n2, v2 = self._campo_rank(e2, s2.get("name", nick2))

        embed = discord.Embed(
            title=f"⚔️  Comparação Solo/Duo",
            description=f"**{s1.get('name', nick1)}**  vs  **{s2.get('name', nick2)}**",
            color=color,
        )
        embed.add_field(name=n1, value=v1, inline=True)
        embed.add_field(name=n2, value=v2, inline=True)
        embed.set_footer(text="Riot Games API  ·  League of Legends")
        await interaction.followup.send(embed=embed)

    # ─── Teamfight Tactics ────────────────────────────────────────────────────

    @app_commands.command(name="tft-rank", description="Exibe o rank de um invocador no TFT")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)")
    async def tft_rank(self, interaction: discord.Interaction, nick: str):
        if await self._canal_invalido(interaction):
            return
            return

        await interaction.response.defer()

        summoner = await self._get_tft_summoner(nick)
        if not summoner:
            await interaction.followup.send(
                "❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).",
                ephemeral=True,
            )
            return

        ranked = await self._get(f"{self.base_url}/tft/league/v1/entries/by-puuid/{summoner['puuid']}")
        entry = (ranked or [None])[0] if ranked else None

        nome, valor = self._campo_rank(entry, "Ranked TFT")
        color = self._cor_por_tier(entry["tier"] if entry else None)

        embed = discord.Embed(
            title=f"🎲  TFT Rank  —  {summoner.get('name', nick)}",
            color=color,
        )
        embed.add_field(name=nome, value=valor, inline=False)
        embed.set_footer(text="Riot Games API  ·  Teamfight Tactics")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tft-historico", description="Exibe o histórico de partidas de TFT")
    @app_commands.describe(nick="Riot ID do invocador (ex: dededao#BR1)", quantidade="Número de partidas (1-10)")
    async def tft_historico(self, interaction: discord.Interaction, nick: str, quantidade: int = 5):
        if await self._canal_invalido(interaction):
            return
            return

        quantidade = max(1, min(quantidade, 10))
        await interaction.response.defer()

        summoner = await self._get_tft_summoner(nick)
        if not summoner:
            await interaction.followup.send(
                "❌ Invocador não encontrado. Use o formato **Nome#TAG** (ex: `dededao#BR1`).",
                ephemeral=True,
            )
            return

        match_ids = await self._get(
            f"{self.regional_url}/tft/match/v1/matches/by-puuid/{summoner['puuid']}/ids",
            params={"count": quantidade},
        )
        if not match_ids:
            await interaction.followup.send("❌ Histórico não encontrado.", ephemeral=True)
            return

        matches = await asyncio.gather(
            *[self._get(f"{self.regional_url}/tft/match/v1/matches/{mid}") for mid in match_ids]
        )

        lugar_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

        embed = discord.Embed(
            title=f"🎲  TFT Histórico  —  {summoner.get('name', nick)}",
            color=discord.Color.from_rgb(48, 197, 176),
        )

        for match in matches:
            if not match:
                continue
            participant = next(
                (p for p in match["info"]["participants"] if p["puuid"] == summoner["puuid"]),
                None,
            )
            if not participant:
                continue

            col = participant["placement"]
            nivel = participant.get("level", "?")
            emoji = lugar_emojis[col - 1] if 1 <= col <= 8 else "💀"

            traits_ativos = [
                t["name"].split("_")[-1]
                for t in participant.get("traits", [])
                if t.get("tier_current", 0) > 0
            ][:4]
            traits_str = "  ·  ".join(traits_ativos) if traits_ativos else "—"

            embed.add_field(
                name=f"{emoji}  {col}º lugar  ·  Nível {nivel}",
                value=f"🧬  {traits_str}",
                inline=False,
            )

        if not embed.fields:
            embed.description = "Nenhuma partida encontrada."

        embed.set_footer(text="Riot Games API  ·  Teamfight Tactics")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RiotCog(bot))
