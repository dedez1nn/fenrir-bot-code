"""Comandos de matchup, counters e runas de League of Legends (dados do OP.GG)."""
from __future__ import annotations

import asyncio
import io
import re
import unicodedata

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from PIL import Image

from services.opgg import (
    ROLES,
    CounterData,
    OpggClient,
    OpggError,
    OpggNotFound,
    RuneBuild,
    RuneData,
    normalize_role,
    slugify,
)
from services.rune_insight import Opponent, build_reasons, riot_tips
from services.rune_image import (
    SHARD_PT,
    Card,
    TREE_PT,
    build_rune_spec,
    TREE_COLOR,
    render_rune_page,
    required_urls,
)

E = "\u001b"  # ESC para ANSI nos code blocks do Discord

MIN_GAMES_RELIABLE = 100     # abaixo disso, avisa amostra pequena
MIN_GAMES_RANKING = 100      # mínimo de jogos para entrar em rankings de counters
SOURCE_TEXT = "Dados: OP.GG  ·  Emerald+ Global"

ROLE_LABELS = {"top": "Topo", "jungle": "Selva", "mid": "Meio", "adc": "Atirador", "support": "Suporte"}
ROLE_EMOJIS = {"top": "🛡️", "jungle": "🌿", "mid": "🔮", "adc": "🏹", "support": "💚"}

TREE_EMOJI = {"Precision": "🟡", "Domination": "🔴", "Sorcery": "🟣",
              "Resolve": "🟢", "Inspiration": "🔵"}

MEDALS = ["🥇", "🥈", "🥉"]

COLOR_WIN = discord.Color.from_rgb(46, 204, 113)
COLOR_LOSE = discord.Color.from_rgb(231, 76, 60)
COLOR_EVEN = discord.Color.from_rgb(241, 196, 15)
COLOR_NEUTRAL = discord.Color.from_rgb(88, 101, 242)


# ─── Helpers de formatação (puros, testáveis) ────────────────────────────────

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def fmt_pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def wr_color_code(wr: float) -> str:
    if wr >= 53:
        return f"{E}[1;92m"
    if wr >= 50:
        return f"{E}[92m"
    if wr >= 47:
        return f"{E}[1;93m"
    return f"{E}[1;91m"


def wr_bar(wr: float, size: int = 16) -> str:
    filled = max(0, min(size, round(wr / 100 * size)))
    c, rst, dim = wr_color_code(wr), f"{E}[0m", f"{E}[90m"
    return f"{c}{'█' * filled}{rst}{dim}{'░' * (size - filled)}{rst}"


def sample_note(games: int) -> str:
    if games < 30:
        return "⚠️ Amostra muito pequena, ignore o win rate."
    if games < MIN_GAMES_RELIABLE:
        return "⚠️ Amostra pequena, use com cautela."
    return ""


def verdict(name_a: str, name_b: str, wr_a: float) -> tuple[str, discord.Color]:
    diff = wr_a - 50
    if abs(diff) < 1.0:
        return f"⚖️ **Matchup equilibrado** entre {name_a} e {name_b}", COLOR_EVEN
    leader, lead = (name_a, diff) if diff > 0 else (name_b, -diff)
    force = "leve vantagem" if lead < 2.5 else "vantagem" if lead < 5 else "grande vantagem"
    color = COLOR_WIN if diff > 0 else COLOR_LOSE
    icon = "🟢" if diff > 0 else "🔴"
    return f"{icon} **{leader}** tem {force} (**{fmt_pct(50 + lead)}** de vitória)", color


def role_tag(role: str) -> str:
    return f"{ROLE_EMOJIS.get(role, '🎮')} {ROLE_LABELS.get(role, role.title())}"


def rune_lines(build: RuneBuild, perk_names: dict[int, str]) -> str:
    """Bloco de texto com a página de runas, nomes traduzidos quando possível."""
    names = list(build.primary_perks) + list(build.secondary_perks) + list(build.shards)
    ids = build.perk_ids if len(build.perk_ids) == len(names) else []
    if ids:
        names = [
            SHARD_PT.get(i) if i in SHARD_PT else perk_names.get(i, n)
            for i, n in zip(ids, names)
        ]
    n_p, n_s = len(build.primary_perks), len(build.secondary_perks)
    primary, secondary, shards = names[:n_p], names[n_p:n_p + n_s], names[n_p + n_s:]
    t1, t2 = TREE_PT.get(build.primary_tree, build.primary_tree), TREE_PT.get(build.secondary_tree, build.secondary_tree)
    e1, e2 = TREE_EMOJI.get(build.primary_tree, "⚪"), TREE_EMOJI.get(build.secondary_tree, "⚪")
    lines = [
        f"{e1} **{t1}**  ·  ⭐ **{primary[0]}**" if primary else f"{e1} **{t1}**",
        f"> {' · '.join(primary[1:])}" if len(primary) > 1 else "",
        f"{e2} **{t2}**",
        f"> {' · '.join(secondary)}" if secondary else "",
        f"🔹 {' · '.join(shards)}" if shards else "",
    ]
    return "\n".join(l for l in lines if l)


def keystone_name(build: RuneBuild, perk_names: dict[int, str]) -> str:
    return perk_names.get(build.perk_ids[0], build.keystone) if build.perk_ids else build.keystone


def rune_stats_line(build: RuneBuild) -> str:
    return f"📈 **{fmt_pct(build.win_rate)}** de vitória  ·  🎮 {fmt_int(build.play)} jogos"


# ─── Cog ─────────────────────────────────────────────────────────────────────

class LolMatchupCog(commands.Cog):
    """/lol-matchup, /lol-runas e /lol-counters."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.opgg = OpggClient()
        self.ddragon_version: str | None = None
        self.champions: dict[str, dict] = {}     # id DDragon -> {"id","name"}
        self._index: dict[str, str] = {}         # nome/id normalizado -> id DDragon
        self.perk_names: dict[int, str] = {}     # id da runa -> nome pt_BR
        self.perk_info: dict[int, dict] = {}     # id -> {name, icon, short, tree_id}
        self.tree_info: dict[int, dict] = {}     # id da árvore -> {name, icon, slots}
        self._icon_bytes: dict[str, bytes] = {}  # cache de ícones baixados
        self._page_cache: dict[tuple, bytes] = {}  # cache das imagens renderizadas
        self._detail_cache: dict[str, dict] = {}   # dicas oficiais por campeão
        self._loaded = False
        self._load_lock = asyncio.Lock()

    # ── Data Dragon ──────────────────────────────────────────────────────────

    async def _ensure_static(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            timeout = aiohttp.ClientTimeout(total=15)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get("https://ddragon.leagueoflegends.com/api/versions.json") as r:
                        version = (await r.json())[0]
                    base = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/pt_BR"
                    async with s.get(f"{base}/champion.json") as r:
                        champs = (await r.json())["data"]
                    async with s.get(f"{base}/runesReforged.json") as r:
                        trees = await r.json()
            except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, IndexError, ValueError):
                return  # tenta de novo na próxima chamada
            self.ddragon_version = version
            self.champions = {c["id"]: {"id": c["id"], "name": c["name"]} for c in champs.values()}
            self._index = {}
            for c in self.champions.values():
                self._index[_norm(c["name"])] = c["id"]
                self._index[_norm(c["id"])] = c["id"]
            self._index.update({"wukong": "MonkeyKing", "nunu": "Nunu", "renata": "Renata"})
            self.perk_names = {
                r["id"]: r["name"]
                for t in trees for slot in t["slots"] for r in slot["runes"]
            }
            self.perk_info = {
                r["id"]: {"name": r["name"], "icon": r["icon"], "short": r.get("shortDesc", ""), "tree_id": t["id"]}
                for t in trees for slot in t["slots"] for r in slot["runes"]
            }
            self.tree_info = {
                t["id"]: {"name": t["name"], "icon": t["icon"],
                          "slots": [[r["id"] for r in slot["runes"]] for slot in t["slots"]]}
                for t in trees
            }
            self._loaded = True

    def resolve_champion(self, text: str) -> dict | None:
        key = _norm(text)
        if key in self._index:
            return self.champions[self._index[key]]
        cands = [cid for k, cid in self._index.items() if key and k.startswith(key)]
        return self.champions[cands[0]] if len(set(cands)) == 1 else None

    def _champ_icon(self, champ_id: str) -> str:
        v = self.ddragon_version or "14.24.1"
        return f"https://ddragon.leagueoflegends.com/cdn/{v}/img/champion/{champ_id}.png"

    async def _autocomplete_champion(self, interaction: discord.Interaction, current: str):
        await self._ensure_static()
        key = _norm(current)
        found = sorted(
            (c for c in self.champions.values() if not key or key in _norm(c["name"])),
            key=lambda c: (not _norm(c["name"]).startswith(key), c["name"]),
        )
        return [app_commands.Choice(name=c["name"], value=c["name"]) for c in found[:25]]

    async def _autocomplete_role(self, interaction: discord.Interaction, current: str):
        cur = current.lower()
        return [
            app_commands.Choice(name=ROLE_LABELS[r], value=r)
            for r in ROLES if not cur or cur in r or cur in ROLE_LABELS[r].lower()
        ]

    # ── Respostas de erro ────────────────────────────────────────────────────

    @staticmethod
    def _erro(titulo: str, texto: str) -> discord.Embed:
        return discord.Embed(title=f"❌  {titulo}", description=texto, color=COLOR_LOSE)

    async def _resolver(self, interaction: discord.Interaction, nome: str, label: str = "Campeão"):
        champ = self.resolve_champion(nome)
        if champ is None:
            await interaction.followup.send(
                embed=self._erro(f"{label} não encontrado",
                                 f"Não achei **{nome}**. Use o autocomplete para escolher o campeão."),
                ephemeral=True,
            )
        return champ

    async def _falha_opgg(self, interaction: discord.Interaction, exc: OpggError, contexto: str) -> None:
        if isinstance(exc, OpggNotFound):
            texto = f"O OP.GG não tem dados para {contexto}. Confira a role e tente de novo."
        else:
            texto = "Não consegui consultar o OP.GG agora. Tente novamente em alguns minutos."
        await interaction.followup.send(embed=self._erro("Sem dados", texto), ephemeral=True)

    # ── Construção dos embeds ────────────────────────────────────────────────

    def _rune_field(self, titulo: str, runes: RuneData | None) -> tuple[str, str]:
        if runes is None or not runes.builds:
            return titulo, "_Sem dados de runas para este matchup._"
        top = runes.builds[0]
        extra = sample_note(top.play)
        body = f"{rune_lines(top, self.perk_names)}\n\n{rune_stats_line(top)}"
        return titulo, body + (f"\n{extra}" if extra else "")

    # ── Imagem da página de runas ────────────────────────────────────────────

    async def _fetch_icon(self, session: aiohttp.ClientSession, url: str) -> Image.Image | None:
        data = self._icon_bytes.get(url)
        if data is None:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.read()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return None
            self._icon_bytes[url] = data
        try:
            return Image.open(io.BytesIO(data)).convert("RGBA")
        except OSError:
            return None

    async def _champ_detail(self, champ_id: str) -> dict:
        """Dicas oficiais (allytips/enemytips) e classes do campeão, em pt-BR. {} se indisponível."""
        if champ_id in self._detail_cache:
            return self._detail_cache[champ_id]
        v = self.ddragon_version
        if not v:
            return {}
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/pt_BR/champion/{champ_id}.json") as r:
                    if r.status != 200:
                        return {}
                    data = (await r.json())["data"][champ_id]
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError):
            return {}
        detail = {"allytips": data.get("allytips", []), "enemytips": data.get("enemytips", []),
                  "tags": data.get("tags", [])}
        self._detail_cache[champ_id] = detail
        return detail

    async def _cards_for(self, champ: dict, build: RuneBuild, general: RuneBuild | None = None,
                         versus: dict | None = None) -> list[Card]:
        """Cards da faixa inferior: motivo da página, como jogar e cuidado com o adversário."""
        mine = await self._champ_detail(champ["id"])
        theirs = await self._champ_detail(versus["id"]) if versus else {}
        opponent = Opponent(versus["name"], tuple(theirs.get("tags", []))) if versus else None
        cards: list[Card] = []
        reasons = build_reasons(build, self.perk_names, general, opponent)
        if reasons:
            titulo = "Por que essa página?" if not versus else f"Por que essa página contra {versus['name']}?"
            cards.append(Card(titulo, reasons, accent=(214, 180, 96), wide=True))
        play = riot_tips(mine.get("allytips"))
        if play:
            cards.append(Card(f"Como jogar de {champ['name']}", play, accent=(96, 204, 132)))
        careful = riot_tips(theirs.get("enemytips")) if versus else []
        if careful:
            cards.append(Card(f"Cuidado com {versus['name']}", careful, accent=(226, 84, 92)))
        return cards

    async def _page_png(self, build: RuneBuild, cards: list[Card] | None = None) -> bytes | None:
        """PNG da página de runas no estilo do cliente (None se não for possível gerar)."""
        cards = cards or []
        key = (tuple(build.perk_ids), tuple((c.title, tuple(c.items)) for c in cards))
        if key in self._page_cache:
            return self._page_cache[key]
        urls = required_urls(build, self.perk_info, self.tree_info)
        if not urls:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                loaded = await asyncio.gather(*(self._fetch_icon(session, u) for u in urls))
            images = {u: img for u, img in zip(urls, loaded) if img is not None}

            def work() -> bytes:
                spec = build_rune_spec(build, self.perk_info, self.tree_info, images)
                spec.cards = cards
                return render_rune_page(spec)

            png = await asyncio.to_thread(work)
        except (ValueError, KeyError, OSError):
            return None
        if len(self._page_cache) >= 200:
            self._page_cache.clear()
        self._page_cache[key] = png
        return png

    async def _page_file(self, build: RuneBuild, filename: str,
                         cards: list[Card] | None = None) -> discord.File | None:
        png = await self._page_png(build, cards)
        return discord.File(io.BytesIO(png), filename=filename) if png else None

    def rune_embed(self, titulo: str, build: RuneBuild, filename: str) -> discord.Embed:
        aviso = sample_note(build.play)
        embed = discord.Embed(
            title=titulo,
            description=rune_stats_line(build) + (f"\n{aviso}" if aviso else ""),
            color=discord.Color.from_rgb(*TREE_COLOR.get(build.primary_tree, (88, 101, 242))),
        )
        embed.set_image(url=f"attachment://{filename}")
        return embed

    def embed_matchup(self, a: dict, b: dict, role: str, counters: CounterData,
                      runes_a: RuneData | None, runes_b: RuneData | None,
                      text_runes: bool = True) -> discord.Embed:
        entry = counters.find(_norm_key(b["id"]))
        if entry is None:
            raise OpggNotFound("matchup sem dados")
        wr_a = entry.win_rate
        wr_b = round(100 - wr_a, 2)
        texto, cor = verdict(a["name"], b["name"], wr_a)

        embed = discord.Embed(
            title=f"⚔️  {a['name']}  vs  {b['name']}",
            description=f"{role_tag(role)}  ·  Patch **{counters.patch}**\n\n{texto}",
            color=cor,
        )
        embed.set_author(name=a["name"], icon_url=self._champ_icon(a["id"]))
        embed.set_thumbnail(url=self._champ_icon(b["id"]))

        nome_w = max(len(a["name"]), len(b["name"]))
        barras = (
            f"```ansi\n"
            f"{a['name']:<{nome_w}}  {wr_bar(wr_a)}  {wr_color_code(wr_a)}{fmt_pct(wr_a)}{E}[0m\n"
            f"{b['name']:<{nome_w}}  {wr_bar(wr_b)}  {wr_color_code(wr_b)}{fmt_pct(wr_b)}{E}[0m\n"
            f"```"
        )
        embed.add_field(name="📊  Taxa de vitória no confronto", value=barras, inline=False)

        aviso = sample_note(entry.play)
        embed.add_field(
            name="🎮  Amostra",
            value=f"**{fmt_int(entry.play)}** partidas analisadas" + (f"\n{aviso}" if aviso else ""),
            inline=False,
        )

        if text_runes:
            n1, v1 = self._rune_field(f"🔮  Runas de {a['name']}", runes_a)
            n2, v2 = self._rune_field(f"🔮  Runas de {b['name']}", runes_b)
            embed.add_field(name=n1, value=v1, inline=True)
            embed.add_field(name=n2, value=v2, inline=True)

        embed.set_footer(text=SOURCE_TEXT)
        return embed

    def embed_runas(self, champ: dict, runes: RuneData, versus: dict | None,
                    text_builds: bool = True) -> discord.Embed:
        alvo = f" vs {versus['name']}" if versus else ""
        embed = discord.Embed(
            title=f"🔮  Runas de {champ['name']}{alvo}",
            description=(
                f"{role_tag(runes.role)}  ·  Patch **{runes.patch}**\n"
                f"Páginas mais jogadas  ·  **{fmt_int(runes.total_play)}** partidas"
            ),
            color=COLOR_NEUTRAL,
        )
        embed.set_author(name=champ["name"], icon_url=self._champ_icon(champ["id"]))
        top = runes.builds[0]
        if top.keystone_image:
            embed.set_thumbnail(url=top.keystone_image)
        for i, build in enumerate(runes.builds[:3] if text_builds else []):
            aviso = sample_note(build.play)
            embed.add_field(
                name=f"{MEDALS[i]}  {keystone_name(build, self.perk_names)}",
                value=f"{rune_lines(build, self.perk_names)}\n\n{rune_stats_line(build)}"
                      + (f"\n{aviso}" if aviso else ""),
                inline=False,
            )
        embed.set_footer(text=SOURCE_TEXT)
        return embed

    def embed_counters(self, champ: dict, counters: CounterData) -> discord.Embed:
        validos = [e for e in counters.entries if e.play >= MIN_GAMES_RANKING]
        fortes = sorted(validos, key=lambda e: e.win_rate, reverse=True)[:5]
        fracos = sorted(validos, key=lambda e: e.win_rate)[:5]

        def linhas(lista, sinal):
            if not lista:
                return "_Sem dados suficientes._"
            return "\n".join(
                f"{sinal} **{e.name}**  ·  {fmt_pct(e.win_rate)}  ·  {fmt_int(e.play)} jogos"
                for e in lista
            )

        embed = discord.Embed(
            title=f"🛡️  Matchups de {champ['name']}",
            description=f"{role_tag(counters.role)}  ·  Patch **{counters.patch}**\n"
                        f"Mínimo de {MIN_GAMES_RANKING} partidas por confronto.",
            color=COLOR_NEUTRAL,
        )
        embed.set_author(name=champ["name"], icon_url=self._champ_icon(champ["id"]))
        embed.add_field(name="🟢  Forte contra", value=linhas(fortes, "▲"), inline=False)
        embed.add_field(name="🔴  Fraco contra", value=linhas(fracos, "▼"), inline=False)
        embed.set_footer(text=SOURCE_TEXT)
        return embed

    # ── Comandos ─────────────────────────────────────────────────────────────

    @app_commands.command(name="lol-matchup", description="Compara dois campeões: vitória no confronto e runas de cada um")
    @app_commands.describe(campeao="Seu campeão", vs="Campeão adversário", role="Rota (padrão: a mais jogada)")
    @app_commands.autocomplete(campeao=_autocomplete_champion, vs=_autocomplete_champion, role=_autocomplete_role)
    async def lol_matchup(self, interaction: discord.Interaction, campeao: str, vs: str, role: str | None = None):
        if await self.bot.guard_channel(interaction):
            return
        await interaction.response.defer()
        await self._ensure_static()

        a = await self._resolver(interaction, campeao)
        b = await self._resolver(interaction, vs, "Adversário") if a else None
        if not a or not b:
            return
        if a["id"] == b["id"]:
            await interaction.followup.send(
                embed=self._erro("Mesmo campeão", "Escolha dois campeões diferentes."), ephemeral=True)
            return
        role_n = normalize_role(role) if role else None
        if role and role_n is None:
            await interaction.followup.send(
                embed=self._erro("Rota inválida", "Use: topo, selva, meio, atirador ou suporte."), ephemeral=True)
            return

        slug_a, slug_b = slugify(a["id"]), slugify(b["id"])
        try:
            counters = await self.opgg.get_counters(slug_a, role_n)
            entry = counters.find(slug_b)
            if entry is None:
                raise OpggNotFound("confronto sem amostra")
            runes_a, runes_b, general_a, general_b = await asyncio.gather(
                self._runes_or_none(slug_a, counters.role, slug_b),
                self._runes_or_none(slug_b, counters.role, slug_a),
                self._runes_or_none(slug_a, counters.role, None),   # página geral, para comparar
                self._runes_or_none(slug_b, counters.role, None),
            )
            embed = self.embed_matchup(a, b, counters.role, counters, runes_a, runes_b, text_runes=False)
        except OpggError as exc:
            await self._falha_opgg(interaction, exc, f"**{a['name']} vs {b['name']}** nessa rota")
            return

        embeds, files = [embed], []
        sides = ((a, b, runes_a, general_a, "runas_a.png"), (b, a, runes_b, general_b, "runas_b.png"))

        async def page_for(champ, rival, runes, general, fn):
            if not (runes and runes.builds):
                return None
            top = runes.builds[0]
            cards = await self._cards_for(champ, top, general.builds[0] if general and general.builds else None, rival)
            return await self._page_file(top, fn, cards)

        pages = await asyncio.gather(*(page_for(*side) for side in sides))
        for (champ, _rival, runes, _general, fn), page in zip(sides, pages):
            if page:  # imagem no estilo do cliente
                top = runes.builds[0]
                embeds.append(self.rune_embed(
                    f"🔮  Runas de {champ['name']}  ·  {keystone_name(top, self.perk_names)}", top, fn))
                files.append(page)
            else:     # fallback em texto
                nome, valor = self._rune_field(f"🔮  Runas de {champ['name']}", runes)
                embed.add_field(name=nome, value=valor, inline=True)
        await interaction.followup.send(embeds=embeds, files=files)

    async def _runes_or_none(self, champ: str, role: str, versus: str | None) -> RuneData | None:
        try:
            return await self.opgg.get_runes(champ, role, versus)
        except OpggError:
            return None

    @app_commands.command(name="lol-runas", description="Páginas de runas mais jogadas de um campeão")
    @app_commands.describe(campeao="Campeão", vs="Adversário (opcional, runas específicas do confronto)",
                           role="Rota (padrão: a mais jogada)")
    @app_commands.autocomplete(campeao=_autocomplete_champion, vs=_autocomplete_champion, role=_autocomplete_role)
    async def lol_runas(self, interaction: discord.Interaction, campeao: str,
                        vs: str | None = None, role: str | None = None):
        if await self.bot.guard_channel(interaction):
            return
        await interaction.response.defer()
        await self._ensure_static()

        champ = await self._resolver(interaction, campeao)
        if not champ:
            return
        versus = None
        if vs:
            versus = await self._resolver(interaction, vs, "Adversário")
            if not versus:
                return
        role_n = normalize_role(role) if role else None
        if role and role_n is None:
            await interaction.followup.send(
                embed=self._erro("Rota inválida", "Use: topo, selva, meio, atirador ou suporte."), ephemeral=True)
            return

        slug = slugify(champ["id"])
        try:
            resolved = role_n or (await self.opgg.get_counters(slug)).role
            runes = await self.opgg.get_runes(slug, resolved, slugify(versus["id"]) if versus else None)
            embed = self.embed_runas(champ, runes, versus, text_builds=False)
        except OpggError as exc:
            await self._falha_opgg(interaction, exc, f"runas de **{champ['name']}**")
            return

        embeds, files = [embed], []
        top3 = runes.builds[:3]
        general = None
        if versus:
            g = await self._runes_or_none(slug, resolved, None)
            general = g.builds[0] if g and g.builds else None
        first_cards = await self._cards_for(champ, top3[0], general, versus)
        # as dicas da Riot aparecem só na primeira imagem; as demais levam só o motivo da página
        card_sets = [first_cards] + [
            [c for c in await self._cards_for(champ, b, general, versus) if c.wide] for b in top3[1:]
        ]
        pages = await asyncio.gather(*(
            self._page_file(b, f"runas_{i}.png", card_sets[i]) for i, b in enumerate(top3)
        ))
        for i, (build, page) in enumerate(zip(top3, pages)):
            titulo = f"{MEDALS[i]}  {keystone_name(build, self.perk_names)}"
            if page:
                embeds.append(self.rune_embed(titulo, build, f"runas_{i}.png"))
                files.append(page)
            else:
                embed.add_field(
                    name=titulo,
                    value=f"{rune_lines(build, self.perk_names)}\n\n{rune_stats_line(build)}",
                    inline=False,
                )
        await interaction.followup.send(embeds=embeds, files=files)

    @app_commands.command(name="lol-counters", description="Contra quem um campeão é forte ou fraco")
    @app_commands.describe(campeao="Campeão", role="Rota (padrão: a mais jogada)")
    @app_commands.autocomplete(campeao=_autocomplete_champion, role=_autocomplete_role)
    async def lol_counters(self, interaction: discord.Interaction, campeao: str, role: str | None = None):
        if await self.bot.guard_channel(interaction):
            return
        await interaction.response.defer()
        await self._ensure_static()

        champ = await self._resolver(interaction, campeao)
        if not champ:
            return
        role_n = normalize_role(role) if role else None
        if role and role_n is None:
            await interaction.followup.send(
                embed=self._erro("Rota inválida", "Use: topo, selva, meio, atirador ou suporte."), ephemeral=True)
            return
        try:
            counters = await self.opgg.get_counters(slugify(champ["id"]), role_n)
            embed = self.embed_counters(champ, counters)
        except OpggError as exc:
            await self._falha_opgg(interaction, exc, f"matchups de **{champ['name']}**")
            return
        await interaction.followup.send(embed=embed)


def _norm_key(ddragon_id: str) -> str:
    return slugify(ddragon_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(LolMatchupCog(bot))
