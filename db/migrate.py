"""Aplicação de migrações SQL e importação automática de JSONs legados.

Fluxo de boot:
1. `apply_migrations(pool)` — aplica todos os arquivos `db/migrations/*.sql` em
   ordem alfabética, registrando em `schema_migrations`. Idempotente.
2. `import_legacy_json(pool)` — se as tabelas críticas estiverem vazias, lê os
   arquivos JSON em `data/` e popula o banco. Não sobrescreve dados existentes.

Ambas as funções são tolerantes a falha: erram silenciosamente com log se o
banco estiver indisponível.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

log = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ─── Migrations ────────────────────────────────────────────────────────────


async def apply_migrations(pool) -> None:
    """Aplica todas as migrações em ordem alfabética. Idempotente."""
    if pool is None:
        log.warning("Pool indisponível — pulando migrations.")
        return

    if not _MIGRATIONS_DIR.exists():
        log.error("Diretório de migrations não encontrado: %s", _MIGRATIONS_DIR)
        return

    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        log.warning("Nenhum arquivo .sql em %s", _MIGRATIONS_DIR)
        return

    async with pool.acquire() as conn:
        # 001 cria a tabela schema_migrations; rodamos sempre 001 primeiro.
        for path in files:
            version = path.stem
            already = False
            try:
                already = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version = $1)",
                    version,
                )
            except Exception:
                already = False  # tabela ainda não existe — primeira execução

            if already:
                log.debug("Migration %s já aplicada — skip.", version)
                continue

            sql = path.read_text(encoding="utf-8")
            log.info("Aplicando migration %s...", version)
            try:
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES ($1) "
                        "ON CONFLICT (version) DO NOTHING",
                        version,
                    )
                log.info("Migration %s aplicada.", version)
            except Exception as exc:
                log.error("Falha ao aplicar migration %s: %s", version, exc)
                raise


# ─── Importação de JSONs legados ──────────────────────────────────────────


def _load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.error("Erro ao ler %s: %s", path, exc)
        return None


def _ts_to_dt(ts: Optional[float]) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


async def _table_is_empty(conn, table: str) -> bool:
    try:
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
        return (count or 0) == 0
    except Exception as exc:
        log.error("Erro ao checar %s: %s", table, exc)
        return False


async def _import_users(conn, raw: Dict[str, Any]) -> int:
    rows = []
    for user_id_str, dados in raw.items():
        try:
            user_id = int(user_id_str)
        except (TypeError, ValueError):
            continue

        premium = dados.get("premium")
        if premium not in (None, "aventureiro", "lendario", "mitico"):
            premium = None

        rows.append(
            (
                user_id,
                int(dados.get("xp", 0) or 0),
                int(dados.get("nivel", 1) or 1),
                dados.get("titulo"),
                bool(dados.get("dobro", False)),
                _ts_to_dt(dados.get("dobro_expiracao")),
                premium,
                None,  # premium_expira — desconhecido nos JSONs antigos
                int(dados.get("coins", 0) or 0),
                int(dados.get("daily_streak", 0) or 0),
                _ts_to_dt(dados.get("last_daily")),
                int(dados.get("total_ganho", 0) or 0),
                dados.get("guild"),
            )
        )

    if not rows:
        return 0

    await conn.executemany(
        """
        INSERT INTO users (
            user_id, xp, nivel, titulo, dobro, dobro_expiracao,
            premium, premium_expira, coins, daily_streak, last_daily,
            total_ganho, guild_name
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        ON CONFLICT (user_id) DO NOTHING
        """,
        rows,
    )
    return len(rows)


async def _import_items(conn, raw: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for item in raw or []:
        try:
            await conn.execute(
                """
                INSERT INTO items (id, nome, preco, descricao, cooldown_h, criado_por)
                VALUES (COALESCE($1, nextval('items_id_seq')), $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                int(item["id"]) if item.get("id") is not None else None,
                str(item.get("nome", "")),
                int(item.get("preco", 0) or 0),
                item.get("descricao"),
                float(item.get("cooldown_h", 0) or 0),
                int(item.get("criado_por", 0) or 0),
            )
            count += 1
        except Exception as exc:
            log.error("Erro ao importar item %s: %s", item, exc)
    if count:
        # Avança a sequência para acima do maior id importado
        try:
            await conn.execute(
                "SELECT setval('items_id_seq', GREATEST((SELECT COALESCE(MAX(id),0) FROM items), 1))"
            )
        except Exception:
            pass
    return count


async def _import_cooldowns(conn, raw: Dict[str, Any]) -> int:
    rows = []
    for user_id_str, items in (raw or {}).items():
        try:
            user_id = int(user_id_str)
        except (TypeError, ValueError):
            continue
        for item_id_str, expires in (items or {}).items():
            try:
                item_id = int(item_id_str)
            except (TypeError, ValueError):
                continue
            dt = _ts_to_dt(expires)
            if dt is None:
                continue
            rows.append((user_id, item_id, dt))

    if not rows:
        return 0

    # Filtra cooldowns que referenciam items inexistentes
    valid_ids = {
        r["id"]
        for r in await conn.fetch("SELECT id FROM items")
    }
    rows = [r for r in rows if r[1] in valid_ids]
    if not rows:
        return 0

    await conn.executemany(
        """
        INSERT INTO cooldowns (user_id, item_id, expires_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, item_id) DO NOTHING
        """,
        rows,
    )
    return len(rows)


async def import_legacy_json(pool, *, force: bool = False) -> Dict[str, int]:
    """Importa JSONs legados quando as tabelas alvo estão vazias.

    Retorna dict com contadores por tabela. Não sobrescreve dados existentes
    (todos os INSERTs são `ON CONFLICT DO NOTHING`). Use `force=True` para
    pular as checagens de tabela vazia (raro — normalmente só faz sentido em
    setup inicial).
    """
    counters = {"users": 0, "items": 0, "cooldowns": 0}

    if pool is None:
        return counters

    async with pool.acquire() as conn:
        # users
        if force or await _table_is_empty(conn, "users"):
            data = _load_json(_DATA_DIR / "user_data.json")
            if isinstance(data, dict) and data:
                counters["users"] = await _import_users(conn, data)
                log.info("Importados %s users de user_data.json", counters["users"])

        # items
        if force or await _table_is_empty(conn, "items"):
            data = _load_json(_DATA_DIR / "loja_data.json")
            # loja_data.json pode ser {"itens": [...], "proximo_id": N} ou uma lista direta
            if isinstance(data, dict):
                data = data.get("itens", [])
            if isinstance(data, list) and data:
                counters["items"] = await _import_items(conn, data)
                log.info("Importados %s items de loja_data.json", counters["items"])

        # cooldowns (depende de items já importados)
        if force or await _table_is_empty(conn, "cooldowns"):
            data = _load_json(_DATA_DIR / "cooldowns_data.json")
            if isinstance(data, dict) and data:
                counters["cooldowns"] = await _import_cooldowns(conn, data)
                log.info("Importados %s cooldowns de cooldowns_data.json", counters["cooldowns"])

    return counters
