"""Texto dos cards: motivo da página de runas e dicas oficiais da Riot.

Nenhum site de estatística publica o "porquê" de uma página de runas, então o motivo é
montado a partir de (1) comparação dos dados do confronto com a página geral do campeão,
(2) uma tabela curada do papel de cada keystone e árvore, e (3) o perfil do adversário
(classes do Data Dragon). São tendências gerais, escritas de forma cautelosa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from services.opgg import RuneBuild
from services.rune_image import TREE_PT

# id da keystone -> (categoria, papel em uma frase)
KEYSTONES: dict[int, tuple[str, str]] = {
    8005: ("burst", "dano explosivo em trocas curtas, punindo quem erra uma habilidade"),
    8008: ("sustained", "velocidade de ataque crescente em lutas longas"),
    8021: ("safe", "cura e velocidade para trocar com segurança na rota"),
    8010: ("sustained", "dano e cura crescentes em lutas prolongadas"),
    8112: ("burst", "rajada rápida de dano para abater alvos"),
    8128: ("burst", "dano que cresce com abates, forte em rotas agressivas"),
    9923: ("burst", "dano explosivo e velocidade de ataque em engajamentos curtos"),
    8214: ("poke", "escudo e utilidade para aliados e trocas à distância"),
    8229: ("poke", "dano à distância para pressionar a rota"),
    8230: ("mobility", "mobilidade para perseguir e escapar"),
    8437: ("defensive", "vida permanente e cura enquanto troca golpes na rota"),
    8439: ("defensive", "resistências ao iniciar a luta, para aguentar e engajar"),
    8465: ("defensive", "proteção e cura para você e seu aliado"),
    8351: ("poke", "lentidão que ajuda a controlar e perseguir alvos"),
    8360: ("utility", "feitiços de invocador extras para adaptar a situação"),
    8369: ("burst", "ouro e dano extra ao abrir trocas"),
}

# papel de cada árvore quando usada como secundária
TREE_NOTES = {
    "Precision": "reforça o dano sustentado e a velocidade de ataque",
    "Domination": "adiciona dano extra e mobilidade para punir alvos",
    "Sorcery": "dá poke, mobilidade e economia de recursos",
    "Resolve": "aumenta a sobrevivência com vida e resistências",
    "Inspiration": "traz utilidade, como calçados e biscoitos, e economia na rota",
}

# (categoria da keystone, classe do adversário) -> tendência
MATCHUP_RULES: dict[tuple[str, str], str] = {
    ("burst", "tank"): "rajadas curtas rendem menos contra alvos com muita vida e resistência",
    ("sustained", "tank"): "lutas longas compensam a vida alta do adversário",
    ("defensive", "tank"): "dano constante contra ele pede aguentar trocas longas",
    ("burst", "fragile"): "o adversário é frágil, e uma rajada inicial costuma bastar",
    ("sustained", "fragile"): "se você alcançar o alvo, o dano contínuo costuma decidir a troca",
    ("safe", "fragile"): "vale trocar com segurança e punir quando ele errar uma habilidade",
    ("burst", "assassin"): "o adversário também busca explosão, então vence quem acerta primeiro",
    ("defensive", "assassin"): "resistência extra ajuda a sobreviver ao burst do adversário",
    ("sustained", "fighter"): "duelo entre lutadores tende a ser longo, e dano contínuo pesa",
    ("burst", "fighter"): "em duelos curtos contra lutadores, quem abre a troca leva vantagem",
    ("defensive", "fighter"): "aguentar o duelo prolongado costuma valer mais que explosão",
    ("poke", "tank"): "o poke abusa de alvos que precisam chegar perto para lutar",
    ("poke", "fragile"): "o poke mantém o alvo frágil sob pressão na rota",
}

TIPS_MAX = 2


@dataclass(frozen=True)
class Opponent:
    name: str
    tags: tuple[str, ...]


def opponent_class(tags: tuple[str, ...] | list[str]) -> str | None:
    """Classe de combate do adversário. A primeira tag do Data Dragon é a classe principal."""
    mapping = {"Tank": "tank", "Assassin": "assassin", "Mage": "fragile",
               "Marksman": "fragile", "Fighter": "fighter"}
    for tag in tags:
        if tag in mapping:
            return mapping[tag]
    return None


def _pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def _num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def build_reasons(build: RuneBuild, perk_names: dict[int, str], general: RuneBuild | None = None,
                  opponent: Opponent | None = None) -> list[str]:
    """Até 3 frases curtas explicando a página de runas. Nunca levanta exceção por falta de dado."""
    items: list[str] = []
    g_id: int | None = None
    ks_id = build.perk_ids[0] if build.perk_ids else None
    ks_name = perk_names.get(ks_id, build.keystone) if ks_id else build.keystone
    category, role_note = KEYSTONES.get(ks_id, (None, None))

    # 1) o que mudou no confronto (ou o resumo da página)
    if opponent and general and general.perk_ids:
        g_id = general.perk_ids[0]
        g_name = perk_names.get(g_id, general.keystone)
        if g_id != ks_id:
            items.append(f"{ks_name} no lugar de {g_name} (a mais jogada no geral) contra {opponent.name}.")
        else:
            items.append(f"Mesma keystone da página geral ({ks_name}), ajustada para enfrentar {opponent.name}.")
        if build.perk_ids[4:5] and general.perk_ids[4:5] and build.secondary_tree != general.secondary_tree:
            items[-1] += (f" Árvore secundária: {TREE_PT.get(build.secondary_tree, build.secondary_tree)}"
                          f" em vez de {TREE_PT.get(general.secondary_tree, general.secondary_tree)}.")
    elif role_note:
        items.append(f"{ks_name}: {role_note}.")

    # 2) tendência do confronto, ou o papel da keystone quando não há adversário
    rule = None
    if opponent and category:
        cls = opponent_class(opponent.tags)
        rule = MATCHUP_RULES.get((category, cls)) if cls else None
    if rule:
        items.append(f"Contra {opponent.name}, {rule}.")
    elif opponent and role_note:
        items.append(f"{ks_name}: {role_note}.")

    # 3) papel da árvore secundária
    note = TREE_NOTES.get(build.secondary_tree)
    if note:
        items.append(f"{TREE_PT.get(build.secondary_tree, build.secondary_tree)} secundária {note}.")

    # 4) leitura dos números (amostra do próprio confronto ou da página)
    if build.play:
        extra = f"{_pct(build.win_rate)} de vitória em {_num(build.play)} jogos"
        if opponent and general and general.play and g_id is not None and g_id != ks_id:
            extra += f" (a página geral tem {_pct(general.win_rate)})"
        items.append(extra + ".")
    return items[:4]


def trim_tip(tip: str, limit: int = 220) -> str:
    """Encurta a dica cortando só em fim de frase; reticências só se nem a primeira frase couber."""
    tip = " ".join(tip.split())
    if len(tip) <= limit:
        return tip
    sentences = re.split(r"(?<=[.!?])\s+", tip)
    out = ""
    for sent in sentences:
        candidate = f"{out} {sent}".strip()
        if len(candidate) > limit:
            break
        out = candidate
    if out:
        return out
    cut = tip[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def riot_tips(tips: list[str] | None, limit: int = 220) -> list[str]:
    return [trim_tip(t, limit) for t in (tips or [])[:TIPS_MAX] if t and t.strip()]
