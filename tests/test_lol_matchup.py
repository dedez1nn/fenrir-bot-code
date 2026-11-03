import io
import json
from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord.ext import commands

from cogs.apis.lol_matchup import (
    LolMatchupCog,
    fmt_int,
    fmt_pct,
    rune_lines,
    sample_note,
    verdict,
)
from services.opgg import (
    OpggClient,
    OpggNotFound,
    OpggParseError,
    decode_flight,
    normalize_role,
    parse_counters,
    parse_patch,
    parse_role_from_route,
    parse_runes,
    slugify,
)


# ─── Fixtures: HTML sintético no formato Next.js do OP.GG ───────────────────

def make_html(flight: str, patch: str = "16.21") -> str:
    chunk = json.dumps(flight)[1:-1]  # escapa como dentro de uma string JS
    return (
        f"<html><title>X Patch {patch}: foo | OP.GG</title>"
        f'<script>self.__next_f.push([1,"{chunk}"])</script></html>'
    )


def counters_flight(entries, role="top"):
    data = [
        {"play": p, "win": w, "win_rate": wr,
         "champion": {"image_url": f"https://img/{k}.png", "name": k.title(), "key": k}}
        for k, p, w, wr in entries
    ]
    return (
        f'0:{{"c":["","lol","champions","fiora","counters","{role}"],"i":false}}\n'
        f'5f:["$","$L63",null,{{"data":{json.dumps(data, separators=(",", ":"))}}}]\n'
    )


def perk(i, name, active):
    return {"id": i, "name": name, "image_url": f"https://img/{i}.png", "isActive": active}


def rune_build(keystone="Conqueror", play=329, win=151, tree="Precision", sub="Resolve"):
    return {
        "id": 8010, "play": play, "win": win, "pick_rate": 0.5,
        "primary_perk_style": {"id": 8000, "name": tree},
        "perk_sub_style": {"id": 8400, "name": sub},
        "main_runes": [
            [perk(8010, keystone, True), perk(8005, "Press the Attack", False)],
            [perk(9111, "Triumph", True)],
            [perk(9104, "Legend: Alacrity", True)],
            [perk(8299, "Last Stand", True)],
        ],
        "sub_runes": [
            [perk(8242, "Unflinching", True), perk(8444, "Second Wind", False)],
            [perk(8473, "Bone Plating", True)],
        ],
        "shards": [[perk(5008, "Adaptive Force", True)], [perk(5008, "Adaptive Force", True)],
                   [perk(5011, "Health", True)]],
        "importClientData": {"selectedPerkIds": [8010, 9111, 9104, 8299, 8242, 8473, 5008, 5008, 5011]},
    }


def runes_flight(builds):
    page = {"id": 8010, "play": sum(b["play"] for b in builds), "pick_rate": 0.2, "builds": builds}
    return f'51:["$","$L52",null,{{"data":{{"rune_pages":{json.dumps([page], separators=(",", ":"))},"x":1}}}}]\n'


ENTRIES = [
    ("ornn", 1973, 1013, 51.34),
    ("yone", 3520, 1905, 54.12),
    ("malphite", 3424, 1498, 43.75),
    ("rare", 12, 10, 83.33),
]


# ─── services.opgg: parsers ──────────────────────────────────────────────────

class TestParsers:
    def test_decode_flight_roundtrip(self):
        text = counters_flight(ENTRIES)
        assert decode_flight(make_html(text)) == text

    def test_decode_flight_sem_stream(self):
        with pytest.raises(OpggParseError):
            decode_flight("<html></html>")

    def test_patch_e_role(self):
        html = make_html(counters_flight(ENTRIES, role="jungle"))
        assert parse_patch(html) == "16.21"
        assert parse_role_from_route(decode_flight(html)) == "jungle"

    def test_role_sem_rota_usa_position(self):
        flight = '0:{"c":["","lol","champions","fiora","counters"]}\n"positions":[{"name":"TOP"}],"position":"top"}'
        assert parse_role_from_route(flight) == "top"
        assert parse_role_from_route("sem nada") is None

    def test_parse_counters(self):
        data = parse_counters(counters_flight(ENTRIES), "fiora", "top", "16.21")
        assert len(data.entries) == 4
        ornn = data.find("ornn")
        assert (ornn.play, ornn.win, ornn.win_rate) == (1973, 1013, 51.34)
        assert data.find("zed") is None

    def test_parse_counters_sem_dados(self):
        with pytest.raises(OpggNotFound):
            parse_counters("0:{}\n", "fiora", "top", "16.21")

    def test_parse_runes_ordena_por_jogos(self):
        flight = runes_flight([rune_build(play=54, win=27), rune_build(keystone="Grasp", play=329, win=151)])
        data = parse_runes(flight, "fiora", "top", "16.21", versus="ornn")
        assert [b.play for b in data.builds] == [329, 54]
        top = data.builds[0]
        assert top.keystone == "Grasp"
        assert top.win_rate == pytest.approx(45.9, abs=0.01)
        assert top.primary_perks == ["Grasp", "Triumph", "Legend: Alacrity", "Last Stand"]
        assert top.secondary_perks == ["Unflinching", "Bone Plating"]
        assert top.shards == ["Adaptive Force", "Adaptive Force", "Health"]
        assert top.perk_ids[0] == 8010 and len(top.perk_ids) == 9
        assert data.versus == "ornn"

    def test_parse_runes_sem_dados(self):
        with pytest.raises(OpggNotFound):
            parse_runes("0:{}\n", "fiora", "top", "16.21")

    def test_slug_e_role(self):
        assert slugify("MonkeyKing") == "monkeyking"
        assert slugify("KSante") == "ksante"
        assert normalize_role("Suporte") == "support"
        assert normalize_role("bot") == "adc"
        assert normalize_role("xyz") is None
        assert normalize_role(None) is None


# ─── services.opgg: cliente (cache) ──────────────────────────────────────────

class TestClient:
    async def test_cache_evita_segunda_requisicao(self):
        client = OpggClient(min_interval=0)
        client._fetch = AsyncMock(return_value=make_html(counters_flight(ENTRIES)))
        a = await client.get_counters("fiora", "top")
        b = await client.get_counters("fiora", "top")
        assert a is b
        assert client._fetch.await_count == 1

    async def test_resolve_role_pela_rota(self):
        client = OpggClient(min_interval=0)
        client._fetch = AsyncMock(return_value=make_html(counters_flight(ENTRIES, role="mid")))
        assert (await client.get_counters("fiora")).role == "mid"

    async def test_serve_cache_vencido_se_opgg_falhar(self):
        from services.opgg import OpggError
        client = OpggClient(ttl=0, min_interval=0)
        client._fetch = AsyncMock(return_value=make_html(counters_flight(ENTRIES)))
        first = await client.get_counters("fiora", "top")
        client._fetch = AsyncMock(side_effect=OpggError("fora do ar"))
        assert await client.get_counters("fiora", "top") is first


# ─── Formatação ──────────────────────────────────────────────────────────────

class TestFormatacao:
    def test_numeros(self):
        assert fmt_int(35147) == "35.147"
        assert fmt_pct(51.34) == "51,3%"

    def test_amostra(self):
        assert "muito pequena" in sample_note(10)
        assert "pequena" in sample_note(60)
        assert sample_note(500) == ""

    def test_veredito(self):
        txt, _ = verdict("Fiora", "Ornn", 50.4)
        assert "equilibrado" in txt
        txt, cor = verdict("Fiora", "Ornn", 55.0)
        assert "Fiora" in txt and "vantagem" in txt
        txt, cor2 = verdict("Fiora", "Ornn", 45.0)
        assert "Ornn" in txt and cor != cor2

    def test_rune_lines_traduz_e_usa_shards_pt(self):
        build = parse_runes(runes_flight([rune_build()]), "fiora", "top", "16.21").builds[0]
        txt = rune_lines(build, {8010: "Conquistador"})
        assert "Conquistador" in txt
        assert "Força Adaptativa" in txt and "Vida" in txt
        assert "Precisão" in txt and "Determinação" in txt


# ─── Cog ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def cog():
    bot = Mock(spec=commands.Bot)
    bot.guard_channel = AsyncMock(return_value=False)
    c = LolMatchupCog(bot)
    c.champions = {
        "Fiora": {"id": "Fiora", "name": "Fiora"},
        "Ornn": {"id": "Ornn", "name": "Ornn"},
        "MonkeyKing": {"id": "MonkeyKing", "name": "Wukong"},
        "Leblanc": {"id": "Leblanc", "name": "LeBlanc"},
    }
    c._index = {"fiora": "Fiora", "ornn": "Ornn", "wukong": "MonkeyKing", "monkeyking": "MonkeyKing",
                "leblanc": "Leblanc"}
    c._loaded = True
    c.perk_names = {}
    c._champ_detail = AsyncMock(return_value={
        "allytips": ["Dica de uso um. Segunda frase."], "enemytips": ["Dica contra o campeão."],
        "tags": ["Fighter"],
    })
    return c


def fake_fetch(runes_by_champ=None):
    """Simula o OP.GG por URL (a ordem das requisições não importa)."""
    def fetch(url):
        if "/counters" in url:
            return make_html(counters_flight(ENTRIES))
        return make_html(runes_flight([rune_build()]))
    return AsyncMock(side_effect=fetch)


class TestCog:
    def test_resolve_champion(self, cog):
        assert cog.resolve_champion("Wukong")["id"] == "MonkeyKing"
        assert cog.resolve_champion("le blanc")["id"] == "Leblanc"
        assert cog.resolve_champion("fio")["id"] == "Fiora"      # prefixo único
        assert cog.resolve_champion("zzz") is None

    def test_embed_matchup(self, cog):
        counters = parse_counters(counters_flight(ENTRIES), "fiora", "top", "16.21")
        runes_a = parse_runes(runes_flight([rune_build()]), "fiora", "top", "16.21", "ornn")
        embed = cog.embed_matchup(cog.champions["Fiora"], cog.champions["Ornn"], "top", counters, runes_a, None)
        assert embed.title == "⚔️  Fiora  vs  Ornn"
        assert "Patch **16.21**" in embed.description
        names = [f.name for f in embed.fields]
        assert any("Taxa de vitória" in n for n in names)
        assert any("Runas de Fiora" in n for n in names)
        barras = next(f.value for f in embed.fields if "Taxa" in f.name)
        assert "51,3%" in barras and "48,7%" in barras
        sem_dados = next(f.value for f in embed.fields if "Runas de Ornn" in f.name)
        assert "Sem dados" in sem_dados
        assert "OP.GG" in embed.footer.text

    def test_embed_matchup_sem_amostra(self, cog):
        counters = parse_counters(counters_flight(ENTRIES), "fiora", "top", "16.21")
        with pytest.raises(OpggNotFound):
            cog.embed_matchup(cog.champions["Fiora"], cog.champions["MonkeyKing"], "top", counters, None, None)

    def test_embed_counters_filtra_amostra_pequena(self, cog):
        counters = parse_counters(counters_flight(ENTRIES), "fiora", "top", "16.21")
        embed = cog.embed_counters(cog.champions["Fiora"], counters)
        fortes = embed.fields[0].value
        assert "Yone" in fortes and "Rare" not in fortes      # 12 jogos fica de fora
        assert "Malphite" in embed.fields[1].value

    def test_embed_runas(self, cog):
        runes = parse_runes(runes_flight([rune_build()]), "fiora", "top", "16.21", "ornn")
        embed = cog.embed_runas(cog.champions["Fiora"], runes, cog.champions["Ornn"])
        assert "Fiora vs Ornn" in embed.title
        assert embed.fields[0].name.startswith("🥇")
        assert embed.thumbnail.url == "https://img/8010.png"

    async def test_comando_matchup_campeao_invalido(self, cog):
        inter = Mock(spec=discord.Interaction)
        inter.response = Mock(defer=AsyncMock())
        inter.followup = Mock(send=AsyncMock())
        await LolMatchupCog.lol_matchup.callback(cog, inter, "xxxx", "ornn", None)
        inter.followup.send.assert_awaited_once()
        assert inter.followup.send.await_args.kwargs["ephemeral"] is True

    async def test_comando_matchup_fluxo_completo_com_fallback_texto(self, cog):
        cog.opgg._fetch = fake_fetch()
        cog.opgg._min_interval = 0
        cog._page_file = AsyncMock(return_value=None)       # imagem indisponível
        inter = Mock(spec=discord.Interaction)
        inter.response = Mock(defer=AsyncMock())
        inter.followup = Mock(send=AsyncMock())
        await LolMatchupCog.lol_matchup.callback(cog, inter, "fiora", "ornn", "topo")
        kwargs = inter.followup.send.await_args.kwargs
        assert len(kwargs["embeds"]) == 1 and kwargs["files"] == []
        embed = kwargs["embeds"][0]
        assert "Fiora" in embed.title and len(embed.fields) == 4   # barras, amostra, 2 de runas em texto

    async def test_comando_matchup_com_imagens_e_cards(self, cog):
        cog.opgg._fetch = fake_fetch()
        cog.opgg._min_interval = 0
        enviados = []

        async def page_file(build, fn, cards=None):
            enviados.append((fn, cards))
            return discord.File(io.BytesIO(b"png"), filename=fn)

        cog._page_file = page_file
        inter = Mock(spec=discord.Interaction)
        inter.response = Mock(defer=AsyncMock())
        inter.followup = Mock(send=AsyncMock())
        await LolMatchupCog.lol_matchup.callback(cog, inter, "fiora", "ornn", None)
        kwargs = inter.followup.send.await_args.kwargs
        assert len(kwargs["embeds"]) == 3 and len(kwargs["files"]) == 2
        assert kwargs["embeds"][1].image.url == "attachment://runas_a.png"
        assert "Runas de Fiora" in kwargs["embeds"][1].title
        assert len(kwargs["embeds"][0].fields) == 2                 # só barras e amostra
        titulos = [[c.title for c in cards] for _, cards in enviados]
        assert titulos[0] == ["Por que essa página contra Ornn?", "Como jogar de Fiora", "Cuidado com Ornn"]
        assert titulos[1][-1] == "Cuidado com Fiora"

    async def test_comando_runas_com_imagens(self, cog):
        cog.opgg._fetch = AsyncMock(side_effect=lambda url: make_html(
            counters_flight(ENTRIES) if "/counters" in url else
            runes_flight([rune_build(), rune_build(keystone="Grasp", play=54, win=27)])))
        cog.opgg._min_interval = 0
        usados = []

        async def page_file(build, fn, cards=None):
            usados.append((fn, [c.title for c in (cards or [])]))
            return discord.File(io.BytesIO(b"png"), filename=fn)

        cog._page_file = page_file
        inter = Mock(spec=discord.Interaction)
        inter.response = Mock(defer=AsyncMock())
        inter.followup = Mock(send=AsyncMock())
        await LolMatchupCog.lol_runas.callback(cog, inter, "fiora", None, None)
        kwargs = inter.followup.send.await_args.kwargs
        assert len(kwargs["embeds"]) == 3 and len(kwargs["files"]) == 2
        assert kwargs["embeds"][1].title.startswith("🥇")
        # dicas da Riot só na primeira imagem; a segunda leva só o motivo
        assert usados[0][1] == ["Por que essa página?", "Como jogar de Fiora"]
        assert usados[1][1] == ["Por que essa página?"]
