"""Cache e acesso a server_feature_config — feature flags por servidor.

Regra de fallback: sem row no banco → feature habilitada (comportamento atual).
Isso garante que o bot existente não quebre ao receber a nova tabela vazia.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


async def is_feature_enabled(pool, guild_id: int, feature: str) -> bool:
    """Retorna se a feature está habilitada para a guild.

    Sem row → True (backwards compatibility — comportamento atual).
    """
    if pool is None:
        return True
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT enabled FROM server_feature_config "
                "WHERE guild_id = $1 AND feature = $2",
                guild_id,
                feature,
            )
        return bool(row["enabled"]) if row is not None else True
    except Exception as exc:
        log.error("Erro ao verificar feature %s/%s: %s", guild_id, feature, exc)
        return True


async def get_all_features(pool, guild_id: int) -> Dict[str, Dict[str, Any]]:
    """Retorna todas as features configuradas para a guild."""
    if pool is None:
        return {}
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM server_feature_config WHERE guild_id = $1 ORDER BY feature",
                guild_id,
            )
        return {row["feature"]: dict(row) for row in rows}
    except Exception as exc:
        log.error("Erro ao carregar features para %s: %s", guild_id, exc)
        return {}


async def set_feature_enabled(pool, guild_id: int, feature: str, enabled: bool) -> None:
    """Habilita ou desabilita uma feature para a guild."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO server_feature_config (guild_id, feature, enabled, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (guild_id, feature) DO UPDATE
                SET enabled = EXCLUDED.enabled, updated_at = NOW()
            """,
            guild_id,
            feature,
            enabled,
        )


async def set_feature_config(pool, guild_id: int, feature: str, config: dict) -> None:
    """Salva a config JSONB de uma feature para a guild."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO server_feature_config (guild_id, feature, config, updated_at)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (guild_id, feature) DO UPDATE
                SET config = EXCLUDED.config, updated_at = NOW()
            """,
            guild_id,
            feature,
            json.dumps(config),
        )
