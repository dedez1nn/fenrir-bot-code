import io

from PIL import Image

from services.opgg import RuneBuild
from services.rune_image import (
    DDRAGON_IMG,
    H,
    W,
    build_rune_spec,
    clean_html,
    render_rune_page,
    required_urls,
    wrap_text,
    _font,
)

PERK_INFO = {
    8010: {"name": "Conquistador", "icon": "k/8010.png", "short": "Ganha <b>acúmulos</b>.<br>Cura.", "tree_id": 8000},
    8005: {"name": "Pressione o Ataque", "icon": "k/8005.png", "short": "x", "tree_id": 8000},
    9111: {"name": "Triunfo", "icon": "m/9111.png", "short": "Restaura vida.", "tree_id": 8000},
    9104: {"name": "Lenda", "icon": "m/9104.png", "short": "Velocidade.", "tree_id": 8000},
    8299: {"name": "Até a Morte", "icon": "m/8299.png", "short": "Mais dano.", "tree_id": 8000},
    8242: {"name": "Inabalável", "icon": "m/8242.png", "short": "Armadura.", "tree_id": 8400},
    8473: {"name": "Osso Revestido", "icon": "m/8473.png", "short": "Reduz dano. " * 30, "tree_id": 8400},
}
TREE_INFO = {
    8000: {"name": "Precisão", "icon": "t/8000.png", "slots": [[8005, 8010], [9111], [9104], [8299]]},
    8400: {"name": "Determinação", "icon": "t/8400.png", "slots": [[8242], [8473]]},
}


def make_build(ids=(8010, 9111, 9104, 8299, 8242, 8473, 5008, 5005, 5011)):
    return RuneBuild(
        keystone="Conqueror", keystone_image="", primary_tree="Precision", secondary_tree="Resolve",
        primary_perks=[], secondary_perks=[], shards=[],
        shard_images=["https://s/5008.png", "https://s/5005.png", "https://s/5011.png"],
        perk_ids=list(ids), play=100, win=50, pick_rate=0.1,
    )


def fake_images(build):
    urls = required_urls(build, PERK_INFO, TREE_INFO)
    return {u: Image.new("RGBA", (64, 64), (200, 80, 80, 255)) for u in urls}


def test_clean_html_e_wrap():
    assert clean_html("a <b>b</b><br/>c   d") == "a b c d"
    font = _font("body", 16)
    lines = wrap_text("palavra " * 60, font, 200, 3)
    assert len(lines) == 3 and lines[-1].endswith("…")
    assert all(font.getlength(l) <= 200 for l in lines)
    assert wrap_text("curto", font, 200, 3) == ["curto"]


def test_fit_font_reduz_para_nomes_longos():
    from services.rune_image import _fit_font
    curto = _fit_font("title", "Triunfo", 276, 27, 19)
    longo = _fit_font("title", "Aperto dos Mortos-Vivos", 276, 27, 19)
    assert curto.size == 27 and longo.size < 27
    assert longo.getlength("Aperto dos Mortos-Vivos") <= 276


def test_required_urls_sem_duplicatas_e_sem_alternativas():
    build = make_build()
    urls = required_urls(build, PERK_INFO, TREE_INFO)
    assert len(urls) == len(set(urls))
    assert f"{DDRAGON_IMG}/k/8010.png" in urls          # keystone usada
    assert f"{DDRAGON_IMG}/k/8005.png" not in urls      # alternativas não são baixadas
    assert f"{DDRAGON_IMG}/t/8400.png" in urls          # ícone da árvore secundária
    assert "https://s/5008.png" in urls                 # fragmento


def test_required_urls_build_incompleta():
    assert required_urls(make_build(ids=(8010,)), PERK_INFO, TREE_INFO) == []


def test_build_spec_e_render_png():
    build = make_build()
    spec = build_rune_spec(build, PERK_INFO, TREE_INFO, fake_images(build))
    assert spec.primary.name == "Precisão" and spec.secondary.name == "Determinação"
    assert [a for _, a in spec.primary.keystone_row] == [True]      # só a keystone usada
    assert spec.primary.keystone_desc == "Ganha acúmulos. Cura."
    assert [s.label for s in spec.shards] == ["Força Adaptativa", "Velocidade de Ataque", "Vida"]
    png = render_rune_page(spec)
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG" and img.size == (W, H)


def test_render_tolera_icones_ausentes():
    build = make_build()
    spec = build_rune_spec(build, PERK_INFO, TREE_INFO, {})   # nenhum ícone baixado
    assert Image.open(io.BytesIO(render_rune_page(spec))).size == (W, H)


def test_centered_ignora_margem_transparente():
    from services.rune_image import _centered
    icon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    icon.paste(Image.new("RGBA", (10, 10), (255, 0, 0, 255)), (50, 4))   # arte deslocada no canto
    out = _centered(icon, 100, 0.8)
    assert out.size == (100, 100)
    box = out.getchannel("A").getbbox()
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    assert abs(cx - 50) <= 1 and abs(cy - 50) <= 1                      # centralizada
    assert box[2] - box[0] == 80                                        # ocupa 80% do lado


def test_scaled_art_mantem_horizontal_e_corrige_vertical():
    from services.rune_image import _scaled_art
    icon = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    # arte alta (y 0..60) e assimétrica na horizontal (x 20..99); centro da imagem é (50, 50)
    icon.paste(Image.new("RGBA", (80, 60), (255, 0, 0, 255)), (20, 0))
    out = _scaled_art(icon, 100, 1.0)
    box = out.getchannel("A").getbbox()
    assert box[0] == 20 and box[2] == 100          # horizontal intacta (sem recentralizar pelo bbox)
    assert 0 < box[1] <= 20                        # desceu parcialmente (bbox ideal desceria 20)


def test_scaled_art_circular_nao_move():
    from services.rune_image import _scaled_art
    out = _scaled_art(Image.new("RGBA", (64, 64), (255, 0, 0, 255)), 60, 1.0)
    assert out.getchannel("A").getbbox() == (0, 0, 60, 60)


def test_centered_imagem_vazia():
    from services.rune_image import _centered
    assert _centered(Image.new("RGBA", (64, 64), (0, 0, 0, 0)), 50, 0.9).size == (50, 50)


def test_build_spec_valida_entrada():
    import pytest
    with pytest.raises(ValueError):
        build_rune_spec(make_build(ids=(8010, 9111)), PERK_INFO, TREE_INFO, {})
    with pytest.raises(ValueError):
        build_rune_spec(make_build(ids=(1, 2, 3, 4, 5, 6, 7, 8, 9)), PERK_INFO, TREE_INFO, {})
