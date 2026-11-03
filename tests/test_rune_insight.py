from services.opgg import RuneBuild
from services.rune_image import Card, H, RunePageSpec, Shard, TreeSpec, W, render_rune_page
from services.rune_insight import (
    Opponent,
    build_reasons,
    opponent_class,
    riot_tips,
    trim_tip,
)

NAMES = {8010: "Conquistador", 8005: "Pressione o Ataque", 8437: "Aperto dos Mortos-Vivos"}


def build(ks=8010, tree="Precision", sub="Resolve", play=329, win=151):
    return RuneBuild(
        keystone="x", keystone_image="", primary_tree=tree, secondary_tree=sub,
        primary_perks=[], secondary_perks=[], shards=[], shard_images=[],
        perk_ids=[ks, 9111, 9104, 8299, 8242, 8473, 5008, 5008, 5011],
        play=play, win=win, pick_rate=0.1,
    )


def test_opponent_class_usa_classe_principal():
    assert opponent_class(["Tank", "Fighter"]) == "tank"
    assert opponent_class(["Fighter", "Assassin"]) == "fighter"      # Fiora: lutadora, não assassina
    assert opponent_class(["Marksman"]) == "fragile"
    assert opponent_class(["Support"]) is None
    assert opponent_class([]) is None


def test_trim_tip_corta_em_fim_de_frase():
    tip = "Primeira frase curta. " + "Segunda frase bem longa " * 12 + "fim."
    out = trim_tip(tip, 80)
    assert out == "Primeira frase curta." and "…" not in out
    assert trim_tip("curta.", 80) == "curta."
    unica = "palavra " * 60
    assert trim_tip(unica, 50).endswith("…") and len(trim_tip(unica, 50)) <= 51


def test_riot_tips_limita_quantidade_e_ignora_vazias():
    assert riot_tips(None) == []
    assert riot_tips(["a.", " ", "b.", "c."]) == ["a."]     # só as 2 primeiras, vazia descartada


def test_motivo_keystone_diferente_da_geral():
    items = build_reasons(build(8010), NAMES, general=build(8005, sub="Inspiration"),
                          opponent=Opponent("Ornn", ("Tank", "Fighter")))
    assert "Conquistador no lugar de Pressione o Ataque" in items[0]
    assert "Determinação em vez de Inspiração" in items[0]
    assert any("lutas longas compensam a vida alta" in i for i in items)
    assert any("45,9% de vitória em 329 jogos" in i and "página geral" in i for i in items)


def test_motivo_mesma_keystone():
    items = build_reasons(build(8437, tree="Resolve", sub="Inspiration"), NAMES, general=build(8437),
                          opponent=Opponent("Fiora", ("Fighter", "Assassin")))
    assert "Mesma keystone da página geral" in items[0]
    assert any("aguentar o duelo prolongado" in i for i in items)


def test_motivo_sem_adversario():
    items = build_reasons(build(8010), NAMES)
    assert items[0].startswith("Conquistador: dano e cura crescentes")
    assert not any("Contra" in i for i in items)


def test_motivo_tolera_dados_incompletos():
    vazio = RuneBuild("x", "", "Precision", "Resolve", [], [], [], [], [], 0, 0, 0)
    assert build_reasons(vazio, {}, general=vazio, opponent=Opponent("Ornn", ())) is not None
    assert build_reasons(build(999), NAMES, opponent=Opponent("Ornn", ("Tank",)))   # keystone desconhecida


def test_render_com_cards_aumenta_a_altura():
    from io import BytesIO
    from PIL import Image
    tree = TreeSpec("Precisão", (214, 180, 96), None, "Árvore primária",
                    minors=[], keystone_row=[(None, True)], keystone_name="Conquistador", keystone_desc="x")
    sec = TreeSpec("Determinação", (96, 204, 132), None, "Árvore secundária", minors=[])
    base = RunePageSpec(tree, sec, [Shard(None, "Vida")])
    h0 = Image.open(BytesIO(render_rune_page(base))).size
    assert h0 == (W, H)                                             # sem cards: tamanho original
    base.cards = [Card("Por que?", ["um motivo " * 30, "outro"], wide=True), Card("Dicas", ["a"]), Card("Cuidado", ["b"])]
    w1, h1 = Image.open(BytesIO(render_rune_page(base))).size
    assert w1 == W and h1 > H + 150
