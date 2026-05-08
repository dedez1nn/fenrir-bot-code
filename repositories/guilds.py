"""Repositório para guilds em jogo (Phase 6).

Funções principais:
- build_full_data(pool)  → reconstrói o dict {guild_id: guild_data, "raids_ativas": {...}}
- sync_full_data(pool, dados) → UPSERT atômico de todo o estado de guilds
- add_banco_atomic / sub_banco_atomic → operações financeiras atômicas no banco da guild
- get_premium_usuario / update_guild_name → auxiliares para interação com a tabela users
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ─── Leitura ──────────────────────────────────────────────────────────────────


async def build_full_data(pool) -> Dict[str, Any]:
    """Reconstrói o dict completo de guilds_data a partir do DB.

    Retorna o mesmo formato usado pelos JSONs legados:
    {
        "guild_xxxx": {nome, lider(str), membros, banco, nivel, xp, motto, emoji,
                       convites, cooldowns, aliancas, data_criacao, ultima_raid, data_alianca},
        "raids_ativas": {raid_id: raid_data_dict}
    }
    """
    result: Dict[str, Any] = {"raids_ativas": {}}

    async with pool.acquire() as conn:
        guilds_rows   = await conn.fetch("SELECT * FROM guilds")
        members_rows  = await conn.fetch("SELECT * FROM guild_members")
        invites_rows  = await conn.fetch("SELECT * FROM guild_invites")
        alliance_rows = await conn.fetch("SELECT * FROM guild_alliances")
        raids_rows    = await conn.fetch("SELECT * FROM guild_raids")

    # index members by guild
    members_by_guild: Dict[str, Dict] = {}
    for m in members_rows:
        gid = m["guild_id"]
        members_by_guild.setdefault(gid, {})[str(m["user_id"])] = {
            "cargo":   m["cargo"],
            "entrada": m["entrada"],
            "ativo":   m["ativo"],
        }

    # index invites by guild
    invites_by_guild: Dict[str, Dict] = {}
    for inv in invites_rows:
        gid = inv["guild_id"]
        invites_by_guild.setdefault(gid, {})[inv["invite_id"]] = {
            "usuario":   str(inv["usuario"]),
            "criador":   str(inv["criador"]),
            "data":      inv["data"],
            "expiracao": inv["expiracao"],
        }

    # index alliances by guild
    alliances_by_guild: Dict[str, List[str]] = {}
    for al in alliance_rows:
        alliances_by_guild.setdefault(al["guild_id"], []).append(al["ally_id"])

    # assemble guilds
    for g in guilds_rows:
        gid = g["guild_id"]
        result[gid] = {
            "nome":         g["nome"],
            "lider":        str(g["lider"]),
            "membros":      members_by_guild.get(gid, {}),
            "banco":        g["banco"],
            "nivel":        g["nivel"],
            "xp":           g["xp"],
            "motto":        g["motto"] or "",
            "emoji":        g["emoji"] or "",
            "convites":     invites_by_guild.get(gid, {}),
            "cooldowns":    {},
            "aliancas":     alliances_by_guild.get(gid, []),
            "data_criacao": g["data_criacao"],
            "ultima_raid":  g["ultima_raid"],
            "data_alianca": g["data_alianca"],
        }

    # assemble raids
    for r in raids_rows:
        result["raids_ativas"][r["raid_id"]] = r["data"]

    return result


# ─── Escrita completa (fire-and-forget) ───────────────────────────────────────


async def sync_full_data(pool, dados: Dict[str, Any]) -> None:
    """Sincroniza o dict completo para o DB em uma única transação.

    Upsert todos os registros presentes em `dados` e remove os que deixaram de
    existir.  É chamado de forma assíncrona (fire-and-forget) por salvar_dados().
    """
    guild_ids = [k for k in dados if k != "raids_ativas"]
    raids_ativas = dados.get("raids_ativas", {})

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Remover guilds que não existem mais
            existing = [r["guild_id"] for r in await conn.fetch("SELECT guild_id FROM guilds")]
            to_delete = [g for g in existing if g not in guild_ids]
            for gid in to_delete:
                await conn.execute("DELETE FROM guilds WHERE guild_id = $1", gid)

            for gid, gdata in dados.items():
                if gid == "raids_ativas":
                    continue

                await conn.execute(
                    """
                    INSERT INTO guilds
                        (guild_id, nome, lider, banco, nivel, xp, motto, emoji,
                         data_criacao, ultima_raid, data_alianca, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW())
                    ON CONFLICT (guild_id) DO UPDATE SET
                        nome=EXCLUDED.nome, lider=EXCLUDED.lider,
                        banco=EXCLUDED.banco, nivel=EXCLUDED.nivel,
                        xp=EXCLUDED.xp, motto=EXCLUDED.motto,
                        emoji=EXCLUDED.emoji, ultima_raid=EXCLUDED.ultima_raid,
                        data_alianca=EXCLUDED.data_alianca, updated_at=NOW()
                    """,
                    gid,
                    str(gdata["nome"]),
                    int(gdata["lider"]),
                    int(gdata.get("banco", 0)),
                    int(gdata.get("nivel", 1)),
                    int(gdata.get("xp", 0)),
                    str(gdata.get("motto", "")),
                    str(gdata.get("emoji", "")),
                    float(gdata.get("data_criacao", time.time())),
                    float(gdata.get("ultima_raid", 0)),
                    float(gdata.get("data_alianca", 0)),
                )

                # Replace members
                await conn.execute("DELETE FROM guild_members WHERE guild_id = $1", gid)
                for uid_str, mdata in gdata.get("membros", {}).items():
                    await conn.execute(
                        """
                        INSERT INTO guild_members (guild_id, user_id, cargo, entrada, ativo)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT DO NOTHING
                        """,
                        gid,
                        int(uid_str),
                        str(mdata.get("cargo", "Membro")),
                        float(mdata.get("entrada", time.time())),
                        bool(mdata.get("ativo", True)),
                    )

                # Replace invites
                await conn.execute("DELETE FROM guild_invites WHERE guild_id = $1", gid)
                for inv_id, inv_data in gdata.get("convites", {}).items():
                    await conn.execute(
                        """
                        INSERT INTO guild_invites
                            (invite_id, guild_id, usuario, criador, data, expiracao)
                        VALUES ($1,$2,$3,$4,$5,$6)
                        ON CONFLICT DO NOTHING
                        """,
                        inv_id,
                        gid,
                        int(inv_data["usuario"]),
                        int(inv_data["criador"]),
                        float(inv_data.get("data", time.time())),
                        float(inv_data["expiracao"]),
                    )

                # Replace alliances
                await conn.execute("DELETE FROM guild_alliances WHERE guild_id = $1", gid)
                for ally_id in gdata.get("aliancas", []):
                    await conn.execute(
                        "INSERT INTO guild_alliances (guild_id, ally_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        gid, str(ally_id),
                    )

            # Replace raids
            existing_raids = [r["raid_id"] for r in await conn.fetch("SELECT raid_id FROM guild_raids")]
            to_delete_raids = [r for r in existing_raids if r not in raids_ativas]
            for rid in to_delete_raids:
                await conn.execute("DELETE FROM guild_raids WHERE raid_id = $1", rid)

            for rid, rdata in raids_ativas.items():
                await conn.execute(
                    """
                    INSERT INTO guild_raids (raid_id, data, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (raid_id) DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                    rid,
                    json.dumps(rdata),
                )


# ─── Operações atômicas no banco da guild ─────────────────────────────────────


async def add_banco_atomic(pool, guild_id: str, delta: int) -> int:
    """Adiciona `delta` ao banco da guild atomicamente. Retorna novo saldo."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE guilds SET banco = banco + $2, updated_at = NOW() WHERE guild_id = $1 RETURNING banco",
            guild_id, delta,
        )
    return int(row["banco"]) if row else 0


async def sub_banco_atomic(pool, guild_id: str, amount: int) -> Optional[int]:
    """Subtrai `amount` do banco da guild se houver saldo suficiente.

    Retorna o novo saldo ou None se saldo insuficiente / guild inexistente.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE guilds SET banco = banco - $2, updated_at = NOW()
            WHERE guild_id = $1 AND banco >= $2
            RETURNING banco
            """,
            guild_id, amount,
        )
    return int(row["banco"]) if row else None


# ─── Auxiliares para interação com a tabela users ────────────────────────────


async def get_premium_usuario(pool, user_id: int) -> Optional[str]:
    """Retorna o plano premium de um usuário ou None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT premium FROM users WHERE user_id = $1", user_id
        )
    return row["premium"] if row else None


async def update_guild_name(pool, user_id: int, guild_name: Optional[str]) -> None:
    """Atualiza o campo guild_name da tabela users (upsert)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, guild_name)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET guild_name = $2, updated_at = NOW()
            """,
            user_id, guild_name,
        )


# ─── Operação atômica de XP (auxiliar para doações de raid) ──────────────────


async def remove_xp_atomic(pool, user_id: int, amount: int) -> bool:
    """Subtrai `amount` de XP do usuário se ele tiver saldo suficiente.

    Retorna True se a operação foi realizada, False se XP insuficiente.
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE users SET xp = xp - $2, updated_at = NOW()
            WHERE user_id = $1 AND xp >= $2
            """,
            user_id, amount,
        )
    return result != "UPDATE 0"
