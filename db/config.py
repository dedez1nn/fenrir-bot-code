"""Cache em memória de `server_config`.

Carrega a configuração do servidor uma vez no boot do bot e guarda em memória
com TTL de 5 minutos. A API pode forçar reload chamando `refresh_server_config`
quando salvar alterações no painel.

A `ServerConfig` expõe acesso por atributo (`config.commands_channel_id`) e por
chave (`config["commands_channel_id"]`) para compatibilidade com diferentes
estilos de uso nos cogs.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_TTL_SECONDS = 300


class ServerConfig:
    """Wrapper imutável (do ponto de vista do bot) sobre uma row de server_config."""

    def __init__(self, data: Dict[str, Any]):
        self._data = dict(data)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def __repr__(self) -> str:
        return f"ServerConfig(guild_id={self._data.get('guild_id')!r})"


class _ConfigCache:
    def __init__(self) -> None:
        self._cache: Dict[int, ServerConfig] = {}
        self._loaded_at: Dict[int, float] = {}

    def get(self, guild_id: int) -> Optional[ServerConfig]:
        if guild_id not in self._cache:
            return None
        if time.time() - self._loaded_at[guild_id] > _TTL_SECONDS:
            return None
        return self._cache[guild_id]

    def set(self, guild_id: int, config: ServerConfig) -> None:
        self._cache[guild_id] = config
        self._loaded_at[guild_id] = time.time()

    def invalidate(self, guild_id: int) -> None:
        self._cache.pop(guild_id, None)
        self._loaded_at.pop(guild_id, None)


_cache = _ConfigCache()


async def load_server_config(pool, guild_id: int) -> Optional[ServerConfig]:
    """Carrega `server_config` para a guild, usando cache se ainda válido.

    Retorna `None` se o pool não existir ou a guild não tiver row.
    """
    if pool is None:
        return None

    cached = _cache.get(guild_id)
    if cached is not None:
        return cached

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM server_config WHERE guild_id = $1",
                guild_id,
            )
    except Exception as exc:
        log.error("Erro ao carregar server_config para %s: %s", guild_id, exc)
        return None

    if row is None:
        log.warning("server_config não encontrada para guild_id=%s", guild_id)
        return None

    config = ServerConfig(dict(row))
    _cache.set(guild_id, config)
    return config


async def refresh_server_config(pool, guild_id: int) -> Optional[ServerConfig]:
    """Força reload do banco invalidando o cache."""
    _cache.invalidate(guild_id)
    return await load_server_config(pool, guild_id)
