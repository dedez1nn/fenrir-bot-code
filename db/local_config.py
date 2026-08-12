"""Fallback local (JSON) para configs pequenas quando não há Postgres.

`bot.config` (server_config) só existe em modo DB — não há linha equivalente
em JSON. Para campos pequenos e de baixa frequência de escrita (IDs de canal
de log, categoria etc.) isso é desnecessariamente rígido: sem Postgres, esses
comandos simplesmente recusam salvar qualquer coisa.

Este módulo guarda esse subconjunto de campos em `data/local_config.json`
(chave -> valor, uma única guild — mesma premissa de "Phase 1" já usada em
outros pontos do bot, ex. `AntiSpam._primary_guild_id`). Não substitui
`server_config`: quando `bot.db`/`bot.config` estão disponíveis, o Postgres
continua sendo a fonte de verdade e este arquivo é ignorado.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_PATH = "data/local_config.json"


def _load() -> Dict[str, Any]:
    try:
        if os.path.exists(_PATH):
            with open(_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception as exc:
        log.error("Erro ao carregar %s: %s", _PATH, exc)
    return {}


def _save(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        log.error("Erro ao salvar %s: %s", _PATH, exc)


def get(key: str, default: Any = None) -> Any:
    """Lê um campo do fallback local."""
    return _load().get(key, default)


def set_many(fields: Dict[str, Any]) -> None:
    """Mescla `fields` no fallback local e persiste."""
    data = _load()
    data.update(fields)
    _save(data)


def get_channel_id(bot, key: str, default: Optional[int] = None) -> Optional[int]:
    """Lê um ID de canal: `bot.config` (Postgres) se disponível, senão o fallback local.

    Substitui o padrão repetido `bot.config.get(key) if bot.config else None`
    pelos cogs — mesma prioridade, mas com fallback em JSON para instâncias
    sem Postgres.
    """
    cfg = getattr(bot, "config", None)
    if cfg is not None:
        return cfg.get(key, default)
    return get(key, default)
