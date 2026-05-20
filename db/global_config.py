"""Cache em memória de `global_config`.

Carrega a configuração global do produto uma vez no boot e guarda em memória.
Parâmetros aqui pertencem ao dono do bot (não ao servidor Discord): TTLs,
pool DB, política de conteúdo, etc.

Uso: `await load_global_config(pool)` → `GlobalConfig`.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_DEFAULT_TTL = 300
_cache: Optional["GlobalConfig"] = None
_loaded_at: float = 0.0


class GlobalConfig:
    """Wrapper sobre as rows de global_config."""

    _DEFAULTS: Dict[str, Any] = {
        "primary_guild_id": None,
        "server_config_ttl_s": _DEFAULT_TTL,
        "admin_session_ttl_h": 12,
        "db_pool_min": 2,
        "db_pool_max": 10,
        "content_policy_blocked_terms": [
            "admin", "mod", "staff", "don", "owner", "@", "#", "http", "discord.gg"
        ],
    }

    def __init__(self, data: Dict[str, Any]):
        self._data = {**self._DEFAULTS, **data}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def __repr__(self) -> str:
        return "GlobalConfig(...)"


async def load_global_config(pool) -> GlobalConfig:
    """Carrega global_config do banco, com cache TTL=server_config_ttl_s.

    Retorna um GlobalConfig com defaults caso o pool seja None ou haja erro.
    """
    global _cache, _loaded_at

    if pool is None:
        return GlobalConfig({})

    ttl = _cache.get("server_config_ttl_s", _DEFAULT_TTL) if _cache else _DEFAULT_TTL
    if _cache is not None and (time.time() - _loaded_at) < ttl:
        return _cache

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM global_config")
        data = {row["key"]: row["value"] for row in rows}
        _cache = GlobalConfig(data)
        _loaded_at = time.time()
        return _cache
    except Exception as exc:
        log.error("Erro ao carregar global_config: %s", exc)
        if _cache is not None:
            return _cache
        return GlobalConfig({})


def invalidate_global_config() -> None:
    global _cache, _loaded_at
    _cache = None
    _loaded_at = 0.0
