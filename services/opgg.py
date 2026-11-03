"""Cliente de scraping do OP.GG para matchups e runas de League of Legends.

O OP.GG é um app Next.js (App Router): os dados ficam em JSON dentro de
``self.__next_f.push([1, "..."])`` no próprio HTML. Não há API pública estável,
então os parsers são defensivos e levantam ``OpggParseError`` quando o formato
muda, para o cog responder com uma mensagem amigável.

Boas práticas adotadas (ver política do OP.GG sobre scraping): cache com TTL,
intervalo mínimo entre requisições e citação da fonte nos embeds.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field

import aiohttp

BASE_URL = "https://op.gg/lol/champions"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
CACHE_TTL = 6 * 60 * 60        # 6h: os dados mudam por patch, não por minuto
MIN_INTERVAL = 1.0             # segundos entre requisições ao OP.GG
REQUEST_TIMEOUT = 15

ROLES = ("top", "jungle", "mid", "adc", "support")
_ROLE_ALIASES = {
    "top": "top", "topo": "top",
    "jungle": "jungle", "jg": "jungle", "jungler": "jungle", "selva": "jungle",
    "mid": "mid", "middle": "mid", "meio": "mid",
    "adc": "adc", "bot": "adc", "bottom": "adc", "atirador": "adc",
    "support": "support", "sup": "support", "suporte": "support",
}


class OpggError(Exception):
    """Falha genérica ao consultar o OP.GG (rede, status, timeout)."""


class OpggNotFound(OpggError):
    """Campeão, role ou matchup sem dados no OP.GG."""


class OpggParseError(OpggError):
    """O formato da página mudou e o parser não achou os dados esperados."""


# ─── Modelos ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CounterEntry:
    key: str            # slug do OP.GG (ex: "ornn")
    name: str           # nome de exibição (ex: "Ornn")
    play: int
    win: int            # vitórias do campeão consultado
    win_rate: float     # % de vitória do campeão consultado
    image_url: str = ""


@dataclass(frozen=True)
class CounterData:
    champion: str
    role: str
    patch: str
    entries: list[CounterEntry] = field(default_factory=list)

    def find(self, key: str) -> CounterEntry | None:
        return next((e for e in self.entries if e.key == key), None)


@dataclass(frozen=True)
class RuneBuild:
    keystone: str
    keystone_image: str
    primary_tree: str
    secondary_tree: str
    primary_perks: list[str]     # keystone + 3 menores da árvore primária
    secondary_perks: list[str]   # 2 menores da árvore secundária
    shards: list[str]            # 3 fragmentos
    shard_images: list[str]      # urls dos ícones dos 3 fragmentos
    perk_ids: list[int]          # ids na ordem: keystone, 3 primárias, 2 secundárias, 3 fragmentos
    play: int
    win: int
    pick_rate: float             # 0..1 (dentro do universo consultado)

    @property
    def win_rate(self) -> float:
        return round(100 * self.win / self.play, 2) if self.play else 0.0


@dataclass(frozen=True)
class RuneData:
    champion: str
    role: str
    patch: str
    versus: str | None
    total_play: int
    builds: list[RuneBuild] = field(default_factory=list)


# ─── Utilidades puras (testáveis sem rede) ───────────────────────────────────

def normalize_role(value: str | None) -> str | None:
    if not value:
        return None
    return _ROLE_ALIASES.get(value.strip().lower())


def slugify(ddragon_id: str) -> str:
    """Converte o id do Data Dragon (ex: 'MonkeyKing') no slug do OP.GG."""
    return re.sub(r"[^a-z0-9]", "", ddragon_id.lower())


def decode_flight(html: str) -> str:
    """Junta e decodifica os chunks ``self.__next_f.push`` da página."""
    parts = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    if not parts:
        raise OpggParseError("stream de dados do OP.GG não encontrado")
    try:
        return "".join(json.loads(f'"{p}"') for p in parts)
    except json.JSONDecodeError as exc:
        raise OpggParseError("stream de dados do OP.GG corrompido") from exc


def extract_json(text: str, marker: str, opener: str = "[") -> object | None:
    """Retorna o valor JSON (lista/objeto) que começa em ``opener`` após ``marker``."""
    i = text.find(marker)
    if i < 0:
        return None
    start = text.find(opener, i)
    if start < 0:
        return None
    closer = "]" if opener == "[" else "}"
    depth, in_str, esc = 0, False, False
    for j in range(start, len(text)):
        c = text[j]
        if in_str:
            esc = (c == "\\") and not esc
            if c == '"' and not esc:
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_patch(html: str) -> str:
    m = re.search(r"Patch (\d+\.\d+)", html)
    return m.group(1) if m else "?"


def parse_role_from_route(flight_text: str) -> str | None:
    m = re.search(r'"c":\["","lol","champions","[^"]+","[a-z]+","([a-z]+)', flight_text)
    if m:
        return m.group(1)
    # sem role na URL: o OP.GG escolhe a mais jogada e informa em "position"
    m = re.search(r'"position":"(top|jungle|mid|adc|support)"', flight_text)
    return m.group(1) if m else None


def parse_counters(flight_text: str, champion: str, role: str, patch: str) -> CounterData:
    marker = '"data":[{"play":'
    i = flight_text.find(marker)
    if i < 0:
        raise OpggNotFound(f"sem dados de counters para {champion}/{role}")
    raw = extract_json(flight_text[i:], '"data":[')
    if not isinstance(raw, list):
        raise OpggParseError("lista de counters ilegível")
    entries: list[CounterEntry] = []
    for item in raw:
        try:
            champ = item["champion"]
            entries.append(CounterEntry(
                key=champ["key"], name=champ["name"],
                play=int(item["play"]), win=int(item["win"]),
                win_rate=float(item["win_rate"]),
                image_url=champ.get("image_url", ""),
            ))
        except (KeyError, TypeError, ValueError) as exc:
            raise OpggParseError("entrada de counter inválida") from exc
    return CounterData(champion=champion, role=role, patch=patch, entries=entries)


def _active_names(groups: list[list[dict]]) -> list[str]:
    return [r["name"] for grp in groups for r in grp if r.get("isActive")]


def _active_images(groups: list[list[dict]]) -> list[str]:
    return [r.get("image_url", "") for grp in groups for r in grp if r.get("isActive")]


def parse_runes(flight_text: str, champion: str, role: str, patch: str,
                versus: str | None = None) -> RuneData:
    pages = extract_json(flight_text, '"rune_pages":[')
    if not isinstance(pages, list) or not pages:
        raise OpggNotFound(f"sem dados de runas para {champion}/{role}")
    builds: list[RuneBuild] = []
    total = 0
    for page in pages:
        total += int(page.get("play", 0))
        for b in page.get("builds", []):
            try:
                main = b["main_runes"]
                ks = next((r for r in main[0] if r.get("isActive")), None)
                if ks is None:
                    continue
                primary = _active_names(main)
                secondary = _active_names(b["sub_runes"])
                shards = _active_names(b["shards"])
                builds.append(RuneBuild(
                    keystone=ks["name"], keystone_image=ks.get("image_url", ""),
                    primary_tree=b["primary_perk_style"]["name"],
                    secondary_tree=b["perk_sub_style"]["name"],
                    primary_perks=primary, secondary_perks=secondary, shards=shards,
                    shard_images=_active_images(b["shards"]),
                    perk_ids=[int(i) for i in b.get("importClientData", {}).get("selectedPerkIds", [])],
                    play=int(b["play"]), win=int(b["win"]),
                    pick_rate=float(b.get("pick_rate", 0)),
                ))
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise OpggParseError("build de runas inválida") from exc
    if not builds:
        raise OpggNotFound(f"sem builds de runas para {champion}/{role}")
    builds.sort(key=lambda x: x.play, reverse=True)
    return RuneData(champion=champion, role=role, patch=patch, versus=versus,
                    total_play=total, builds=builds)


# ─── Cliente HTTP com cache e rate limit ─────────────────────────────────────

class OpggClient:
    def __init__(self, ttl: int = CACHE_TTL, min_interval: float = MIN_INTERVAL):
        self._ttl = ttl
        self._min_interval = min_interval
        self._cache: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    def _cached(self, key: str):
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self._ttl:
            return hit[1], False
        return (hit[1], True) if hit else (None, True)  # (valor possivelmente vencido, expirado?)

    async def _fetch(self, url: str) -> str:
        async with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                headers = {"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"}
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
                    async with s.get(url) as resp:
                        if resp.status == 404:
                            raise OpggNotFound("página não encontrada no OP.GG")
                        if resp.status != 200:
                            raise OpggError(f"OP.GG respondeu {resp.status}")
                        return await resp.text()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise OpggError("falha de rede ao consultar o OP.GG") from exc
            finally:
                self._last_request = time.monotonic()

    async def _get_cached(self, key: str, loader):
        value, expired = self._cached(key)
        if value is not None and not expired:
            return value
        try:
            fresh = await loader()
        except OpggError:
            if value is not None:   # serve cache vencido se o OP.GG falhar
                return value
            raise
        self._cache[key] = (time.monotonic(), fresh)
        return fresh

    async def get_counters(self, champion: str, role: str | None = None) -> CounterData:
        async def load() -> CounterData:
            url = f"{BASE_URL}/{champion}/counters" + (f"/{role}" if role else "")
            html = await self._fetch(url)
            text = decode_flight(html)
            resolved = role or parse_role_from_route(text)
            if not resolved:
                raise OpggNotFound(f"role de {champion} não identificada")
            return parse_counters(text, champion, resolved, parse_patch(html))
        return await self._get_cached(f"counters:{champion}:{role}", load)

    async def get_runes(self, champion: str, role: str, versus: str | None = None) -> RuneData:
        async def load() -> RuneData:
            q = f"?target_champion={versus}" if versus else ""
            html = await self._fetch(f"{BASE_URL}/{champion}/runes/{role}{q}")
            return parse_runes(decode_flight(html), champion, role, parse_patch(html), versus)
        return await self._get_cached(f"runes:{champion}:{role}:{versus}", load)
