"""Renderiza a página de runas no estilo do cliente de League of Legends.

A parte de desenho (`render_rune_page`) é pura: recebe imagens PIL já carregadas
e devolve bytes PNG, então é testável sem rede. `build_rune_spec` monta a
especificação a partir de uma `RuneBuild` do OP.GG e dos dados do Data Dragon.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from services.opgg import RuneBuild

DDRAGON_IMG = "https://ddragon.leagueoflegends.com/cdn/img"
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

TREE_PT = {"Precision": "Precisão", "Domination": "Dominação", "Sorcery": "Feitiçaria",
           "Resolve": "Determinação", "Inspiration": "Inspiração"}
TREE_COLOR = {  # cor de destaque por árvore (nome em inglês, como vem do OP.GG)
    "Precision": (214, 180, 96), "Domination": (226, 84, 92), "Sorcery": (140, 156, 240),
    "Resolve": (96, 204, 132), "Inspiration": (92, 196, 214),
}
SHARD_PT = {
    5001: "Vida Escalável", 5005: "Velocidade de Ataque", 5007: "Aceleração de Habilidade",
    5008: "Força Adaptativa", 5010: "Velocidade de Movimento", 5011: "Vida",
    5013: "Tenacidade e Resist. a Lentidão",
}

GOLD = (200, 170, 110)
CREAM = (240, 230, 210)
MUTED = (150, 160, 175)
BG_TOP, BG_BOTTOM = (11, 16, 28), (22, 30, 46)

W, H = 920, 664
COL_W = 400
X_LEFT, X_RIGHT = 44, 476
ROW = 108  # altura de cada runa menor
VERTICAL_NUDGE = 0.6  # fração da correção vertical aplicada à arte das runas
XC = 52    # eixo vertical dos ícones (relativo à coluna)
TEXT = 120  # início do texto (relativo à coluna)


# ─── Modelo de desenho ───────────────────────────────────────────────────────

@dataclass
class Minor:
    icon: Image.Image | None
    name: str
    desc: str = ""


@dataclass
class TreeSpec:
    name: str
    color: tuple[int, int, int]
    icon: Image.Image | None
    label: str
    minors: list[Minor] = field(default_factory=list)
    keystone_row: list[tuple[Image.Image | None, bool]] = field(default_factory=list)
    keystone_name: str = ""
    keystone_desc: str = ""


@dataclass
class Shard:
    icon: Image.Image | None
    label: str


@dataclass
class Card:
    """Flash card da faixa inferior: título e itens de texto (cada item vira um marcador)."""
    title: str
    items: list[str]
    accent: tuple[int, int, int] = GOLD
    wide: bool = False   # ocupa a linha inteira; os demais dividem uma linha entre si


@dataclass
class RunePageSpec:
    primary: TreeSpec
    secondary: TreeSpec
    shards: list[Shard]
    cards: list[Card] = field(default_factory=list)


# ─── Fontes e texto ──────────────────────────────────────────────────────────

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    """kind: 'title' (Marcellus), 'bold' ou 'body' (Lato). Cai para DejaVu se faltar."""
    key = (kind, size)
    if key in _font_cache:
        return _font_cache[key]
    files = {
        "title": ["Marcellus-Regular.ttf", "DejaVuSans-Bold.ttf"],
        "bold": ["Lato-Bold.ttf", "DejaVuSans-Bold.ttf"],
        "body": ["Lato-Regular.ttf", "DejaVuSans.ttf"],
    }[kind]
    font = None
    for name in files:
        try:
            font = ImageFont.truetype(str(FONT_DIR / name), size)
            break
        except OSError:
            continue
    _font_cache[key] = font or ImageFont.load_default()
    return _font_cache[key]


def _fit_font(kind: str, text: str, max_width: int, start: int, minimum: int) -> ImageFont.FreeTypeFont:
    """Maior fonte (de `start` até `minimum`) em que o texto cabe em `max_width`."""
    for size in range(start, minimum - 1, -1):
        font = _font(kind, size)
        if font.getlength(text) <= max_width:
            return font
    return _font(kind, minimum)


def clean_html(text: str) -> str:
    """Remove as tags HTML das descrições do Data Dragon."""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.getlength(trial) <= max_width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.getlength(last + "…") > max_width:
            last = last[:-1].rstrip()
        lines[-1] = last + "…"
    return lines


# ─── Primitivas de desenho ───────────────────────────────────────────────────

def _background(color_l, color_r, height: int = H) -> Image.Image:
    img = Image.new("RGBA", (W, height))
    px = ImageDraw.Draw(img)
    for y in range(height):
        t = y / (height - 1)
        px.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)) + (255,))
    for cx, color in ((X_LEFT + 30, color_l), (X_RIGHT + 30, color_r)):
        glow = Image.new("RGBA", (W, height), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([cx - 230, -170, cx + 230, 230], fill=color + (46,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, height - 1], outline=GOLD + (140,), width=2)
    d.rectangle([8, 8, W - 9, height - 9], outline=GOLD + (50,), width=1)
    return img


def _dim(icon: Image.Image) -> Image.Image:
    rgb = ImageOps.grayscale(icon.convert("RGB")).convert("RGB")
    rgb = Image.eval(rgb, lambda v: int(v * 0.55))
    rgb.putalpha(icon.getchannel("A") if icon.mode == "RGBA" else 255)
    return rgb


def _centered(icon: Image.Image, size: int, fill: float) -> Image.Image:
    """Modo 'glifo': recorta a margem transparente e centraliza o conteúdo visível.

    Para ícones sem fundo que ocupam a imagem toda (árvores e fragmentos): `fill` é a
    fração do diâmetro que o maior lado do glifo ocupa, para caber dentro do círculo.
    """
    rgba = icon.convert("RGBA")
    bbox = rgba.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    scale = (size * fill) / max(rgba.size)
    rgba = rgba.resize((max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))), Image.LANCZOS)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(rgba, ((size - rgba.width) // 2, (size - rgba.height) // 2), rgba)
    return layer


def _scaled_art(icon: Image.Image, size: int, fill: float) -> Image.Image:
    """Modo 'arte': mantém o enquadramento original da Riot (já centrado no eixo da imagem).

    Recortar pelo bounding box desloca a arte na horizontal quando há brilhos assimétricos
    (ex: Conquistador). Por isso a horizontal segue o eixo original; só a vertical recebe uma
    correção parcial, porque o brilho do topo costuma ser maior que o da base.
    """
    src = icon.convert("RGBA")
    side = max(1, round(size * fill))
    bbox = src.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
    dy = 0
    if bbox:
        dy = round((src.height / 2 - (bbox[1] + bbox[3]) / 2) * VERTICAL_NUDGE * side / src.height)
    art = src.resize((side, side), Image.LANCZOS)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(art, ((size - side) // 2, (size - side) // 2 + dy), art)
    return layer


def _paste_icon(canvas: Image.Image, icon: Image.Image | None, cx: int, cy: int, size: int,
                ring: tuple[int, int, int] | None = None, dim: bool = False, glow: bool = False,
                fill: float = 1.0, glyph: bool = False) -> None:
    """Desenha o ícone num disco centrado em (cx, cy)."""
    r = size // 2
    if glow and ring:
        halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14], fill=ring + (120,))
        canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(canvas)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(8, 12, 20, 235))
    if icon is not None:
        pic = _centered(icon, size, fill) if glyph else _scaled_art(icon, size, fill)
        canvas.alpha_composite(_dim(pic) if dim else pic, (cx - r, cy - r))
    if ring:
        d.ellipse([cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2],
                  outline=ring + ((90,) if dim else (255,)), width=3 if not dim else 2)


def _draw_lines(d: ImageDraw.ImageDraw, x: int, y: int, lines: list[str], font, fill, spacing: int) -> int:
    for line in lines:
        d.text((x, y), line, font=font, fill=fill)
        y += spacing
    return y


def _axis_line(canvas: Image.Image, x: int, y1: int, y2: int, color) -> None:
    """Conector vertical no eixo dos ícones (desenhado antes deles, que o cobrem)."""
    ImageDraw.Draw(canvas).line([(x, y1), (x, y2)], fill=color + (130,), width=3)


def _header(canvas: Image.Image, tree: TreeSpec, x0: int, y: int) -> tuple[int, int]:
    """Cabeçalho da árvore. Retorna (y seguinte, cy do ícone)."""
    d = ImageDraw.Draw(canvas)
    cy = y + 30
    _paste_icon(canvas, tree.icon, x0 + XC, cy, 56, ring=None, fill=0.7, glyph=True)
    d.text((x0 + XC + 40, y + 2), tree.name.upper(), font=_font("title", 27), fill=tree.color)
    d.text((x0 + XC + 41, y + 36), tree.label.upper(), font=_font("bold", 13), fill=MUTED)
    return y + 82, cy


def _minor_rows(canvas: Image.Image, tree: TreeSpec, x0: int, y: int, line_from: int) -> int:
    """Desenha as runas menores no eixo e o conector desde `line_from`. Retorna o y final."""
    d = ImageDraw.Draw(canvas)
    if tree.minors:
        _axis_line(canvas, x0 + XC, line_from, y + ROW * (len(tree.minors) - 1) + 30, tree.color)
    for m in tree.minors:
        _paste_icon(canvas, m.icon, x0 + XC, y + 30, 60, ring=tree.color)
        d.text((x0 + TEXT, y - 2), m.name, font=_font("bold", 22), fill=CREAM)
        desc = wrap_text(m.desc, _font("body", 16), COL_W - TEXT, 3)
        _draw_lines(d, x0 + TEXT, y + 28, desc, _font("body", 16), MUTED, 21)
        y += ROW
    return y


CARD_GAP = 16
CARD_PAD = 18
CARD_FONT = 16
CARD_LINE = 22
CARD_MAX_LINES = 11     # por card, somando todos os itens
STRIP_TOP = H - 18      # início da faixa de cards (logo abaixo das colunas)


def _card_lines(card: Card, width: int) -> list[list[str]]:
    """Itens quebrados em linhas, respeitando o limite de linhas do card."""
    font = _font("body", CARD_FONT)
    inner = width - 2 * CARD_PAD - 14
    out: list[list[str]] = []
    budget = CARD_MAX_LINES
    for item in card.items:
        if budget <= 0:
            break
        lines = wrap_text(item, font, inner, min(budget, 5))
        out.append(lines)
        budget -= len(lines)
    return out


def _card_height(card: Card, width: int) -> int:
    body = sum(len(item) * CARD_LINE + 6 for item in _card_lines(card, width))
    return CARD_PAD + 28 + body + CARD_PAD - 4


def _layout_cards(cards: list[Card]) -> list[list[tuple[Card, int, int]]]:
    """Linhas de cards: (card, x, largura). Cards `wide` ocupam uma linha; os outros dividem uma."""
    full = W - 2 * X_LEFT
    rows: list[list[tuple[Card, int, int]]] = []
    narrow: list[Card] = []
    for c in cards:
        if c.wide:
            rows.append([(c, X_LEFT, full)])
        else:
            narrow.append(c)
    if narrow:
        w = (full - CARD_GAP * (len(narrow) - 1)) // len(narrow)
        rows.append([(c, X_LEFT + i * (w + CARD_GAP), w) for i, c in enumerate(narrow)])
    return rows


def _strip_height(rows: list[list[tuple[Card, int, int]]]) -> int:
    if not rows:
        return 0
    heights = [max(_card_height(c, w) for c, _, w in row) for row in rows]
    return sum(heights) + CARD_GAP * (len(rows) - 1)


def _draw_cards(canvas: Image.Image, rows: list[list[tuple[Card, int, int]]], y: int) -> None:
    for row in rows:
        h = max(_card_height(c, w) for c, _, w in row)
        for card, x, w in row:
            overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.rounded_rectangle([x, y, x + w, y + h], radius=12, fill=(255, 255, 255, 14),
                                 outline=card.accent + (70,), width=1)
            od.rounded_rectangle([x, y + 10, x + 4, y + h - 10], radius=2, fill=card.accent + (255,))
            canvas.alpha_composite(overlay)
            d = ImageDraw.Draw(canvas)
            d.text((x + CARD_PAD + 6, y + CARD_PAD - 4), card.title.upper(),
                   font=_font("bold", 14), fill=card.accent)
            ty = y + CARD_PAD + 26
            font = _font("body", CARD_FONT)
            for item in _card_lines(card, w):
                for n, line in enumerate(item):
                    if n == 0:
                        d.text((x + CARD_PAD + 6, ty), "•", font=font, fill=card.accent)
                    d.text((x + CARD_PAD + 20, ty), line, font=font, fill=CREAM)
                    ty += CARD_LINE
                ty += 6
        y += h + CARD_GAP


def render_rune_page(spec: RunePageSpec) -> bytes:
    rows = _layout_cards(spec.cards)
    strip = _strip_height(rows)
    total_h = H if not rows else STRIP_TOP + strip + 30
    canvas = _background(spec.primary.color, spec.secondary.color, total_h)
    d = ImageDraw.Draw(canvas)

    # ── coluna esquerda: árvore primária (keystone e menores no mesmo eixo vertical)
    p, x0 = spec.primary, X_LEFT
    y, hcy = _header(canvas, p, x0, 34)
    y += 24
    d.text((x0 + TEXT, y - 19), "RUNA ESSENCIAL", font=_font("bold", 13), fill=GOLD)
    ks_cy = y + 52
    name_font = _fit_font("title", p.keystone_name, COL_W - TEXT - 4, 27, 19)
    desc = wrap_text(p.keystone_desc, _font("body", 17), COL_W - TEXT, 4)
    minors_y = max(y + 40 + 23 * len(desc), y + 110) + 22
    _axis_line(canvas, x0 + XC, hcy + 28, minors_y + ROW * (len(p.minors) - 1) + 30, p.color)
    icon = next((i for i, active in p.keystone_row if active), None)
    _paste_icon(canvas, icon, x0 + XC, ks_cy, 100, ring=p.color, glow=True)
    d.text((x0 + TEXT, y + 2), p.keystone_name, font=name_font, fill=CREAM)
    _draw_lines(d, x0 + TEXT, y + 40, desc, _font("body", 17), MUTED, 23)
    # as menores reaproveitam o conector já desenhado (line_from no fim da keystone)
    _minor_rows(canvas, p, x0, minors_y, line_from=ks_cy + 50)

    # ── coluna direita: árvore secundária + fragmentos
    s, x0 = spec.secondary, X_RIGHT
    y, hcy = _header(canvas, s, x0, 34)
    y = _minor_rows(canvas, s, x0, y + 14, line_from=hcy + 28) + 8
    d.line([(x0, y), (x0 + COL_W, y)], fill=GOLD + (70,), width=1)
    d.text((x0, y + 14), "FRAGMENTOS", font=_font("bold", 13), fill=GOLD)
    y += 46
    for sh in spec.shards:
        _paste_icon(canvas, sh.icon, x0 + XC, y + 20, 40, ring=GOLD, fill=0.62, glyph=True)
        d.text((x0 + TEXT, y + 7), sh.label, font=_font("bold", 19), fill=CREAM)
        y += 54

    if rows:
        _draw_cards(canvas, rows, STRIP_TOP)

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


# ─── Montagem da especificação a partir dos dados ────────────────────────────

def _tree_of(perk_id: int, perk_info: dict[int, dict]) -> int | None:
    info = perk_info.get(perk_id)
    return info["tree_id"] if info else None


def required_urls(build: RuneBuild, perk_info: dict[int, dict], tree_info: dict[int, dict]) -> list[str]:
    """URLs de ícones necessárias para desenhar a página (sem duplicatas)."""
    urls: list[str] = []
    ids = build.perk_ids
    if len(ids) < 6:
        return urls
    for tree_id in {_tree_of(ids[0], perk_info), _tree_of(ids[4], perk_info)}:
        if tree_id in tree_info:
            urls.append(f"{DDRAGON_IMG}/{tree_info[tree_id]['icon']}")
    urls += [f"{DDRAGON_IMG}/{perk_info[i]['icon']}" for i in ids[:6] if i in perk_info]
    urls += [u for u in build.shard_images if u]
    return list(dict.fromkeys(urls))


def build_rune_spec(build: RuneBuild, perk_info: dict[int, dict], tree_info: dict[int, dict],
                    images: dict[str, Image.Image]) -> RunePageSpec:
    """perk_info: id -> {name, icon, short, tree_id}; tree_info: id -> {name, icon, slots}."""
    ids = build.perk_ids
    if len(ids) != 9:
        raise ValueError("a build precisa ter 9 runas (keystone, 3, 2 e 3 fragmentos)")

    def img(path: str | None) -> Image.Image | None:
        return images.get(f"{DDRAGON_IMG}/{path}") if path else None

    def minor(i: int) -> Minor:
        info = perk_info.get(i, {})
        return Minor(img(info.get("icon")), info.get("name", str(i)), clean_html(info.get("short", "")))

    t1, t2 = tree_info.get(_tree_of(ids[0], perk_info) or -1), tree_info.get(_tree_of(ids[4], perk_info) or -1)
    if not t1 or not t2:
        raise ValueError("árvores de runas não encontradas no Data Dragon")

    def tree_color(name_en: str) -> tuple[int, int, int]:
        return TREE_COLOR.get(name_en, GOLD)

    ks = perk_info.get(ids[0], {})
    primary = TreeSpec(
        name=t1["name"], color=tree_color(build.primary_tree), icon=img(t1["icon"]),
        label="Árvore primária",
        keystone_row=[(img(ks.get("icon")), True)],
        keystone_name=ks.get("name", build.keystone), keystone_desc=clean_html(ks.get("short", "")),
        minors=[minor(i) for i in ids[1:4]],
    )
    secondary = TreeSpec(
        name=t2["name"], color=tree_color(build.secondary_tree), icon=img(t2["icon"]),
        label="Árvore secundária", minors=[minor(i) for i in ids[4:6]],
    )
    shards = [
        Shard(images.get(build.shard_images[n]) if n < len(build.shard_images) else None,
              SHARD_PT.get(sid, str(sid)))
        for n, sid in enumerate(ids[6:9])
    ]
    return RunePageSpec(primary, secondary, shards)
