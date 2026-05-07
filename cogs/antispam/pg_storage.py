"""Storage backed por Postgres (`antispam_users` + `antispam_whitelist`).

Implementa a mesma interface que `JSONStorage` (load/save/guild/user) para que
os módulos de scoring, detector, punisher e cog não precisem mudar. Lazy-load
por guild — toda a guild é carregada na primeira referência e mantida em
cache até o cog descarregar; cada `save()` faz upsert das entradas mutadas.

A camada é resiliente: callers não precisam saber se o backend é JSON ou PG.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set, Tuple

log = logging.getLogger(__name__)


class PgStorage:
    def __init__(self, pool):
        self.pool = pool
        self._lock = asyncio.Lock()
        # {gid_str: {users: {uid_str: state}, whitelist: [uid_str], config_overrides: {}}}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._loaded_guilds: Set[int] = set()
        self._dirty_users: Set[Tuple[int, int]] = set()
        self._dirty_whitelist: Set[int] = set()

    @staticmethod
    def _default_user_state() -> Dict[str, Any]:
        return {
            "score": 0.0,
            "last_event_ts": 0.0,
            "infractions": [],
            "punishments": [],
            "blacklisted": False,
            "recent_messages": [],
        }

    async def _load_guild(self, guild_id: int) -> Dict[str, Any]:
        gid = str(guild_id)
        if guild_id in self._loaded_guilds:
            return self._cache[gid]

        guild_state: Dict[str, Any] = {"users": {}, "whitelist": [], "config_overrides": {}}
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT user_id, score, last_event_ts, infractions,
                           punishments, blacklisted, recent_messages
                    FROM antispam_users
                    WHERE guild_id = $1
                    """,
                    guild_id,
                )
                for r in rows:
                    guild_state["users"][str(r["user_id"])] = {
                        "score": float(r["score"] or 0.0),
                        "last_event_ts": float(r["last_event_ts"] or 0.0),
                        "infractions": list(r["infractions"] or []),
                        "punishments": list(r["punishments"] or []),
                        "blacklisted": bool(r["blacklisted"]),
                        "recent_messages": list(r["recent_messages"] or []),
                    }
                wl_rows = await conn.fetch(
                    "SELECT user_id FROM antispam_whitelist WHERE guild_id = $1",
                    guild_id,
                )
                guild_state["whitelist"] = [str(r["user_id"]) for r in wl_rows]
        except Exception as exc:
            log.error("Erro ao carregar antispam guild %s: %s", guild_id, exc)

        self._cache[gid] = guild_state
        self._loaded_guilds.add(guild_id)
        return guild_state

    # ─── Compat. com JSONStorage ────────────────────────────────────────────

    async def load(self) -> Dict[str, Any]:
        """No-op para compat. Carregamento é por-guild (lazy)."""
        return self._cache

    async def save(self) -> None:
        async with self._lock:
            if not self._dirty_users and not self._dirty_whitelist:
                return
            try:
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        await self._flush_users(conn)
                        await self._flush_whitelists(conn)
                self._dirty_users.clear()
                self._dirty_whitelist.clear()
            except Exception as exc:
                log.error("Erro ao salvar antispam state: %s", exc)

    async def _flush_users(self, conn) -> None:
        if not self._dirty_users:
            return
        rows = []
        for gid, uid in self._dirty_users:
            state = self._cache.get(str(gid), {}).get("users", {}).get(str(uid))
            if state is None:
                continue
            rows.append(
                (
                    gid,
                    uid,
                    float(state.get("score", 0.0) or 0.0),
                    float(state.get("last_event_ts", 0.0) or 0.0),
                    list(state.get("infractions", []) or []),
                    list(state.get("punishments", []) or []),
                    bool(state.get("blacklisted", False)),
                    list(state.get("recent_messages", []) or []),
                )
            )
        if not rows:
            return
        await conn.executemany(
            """
            INSERT INTO antispam_users (
                guild_id, user_id, score, last_event_ts,
                infractions, punishments, blacklisted, recent_messages, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                score           = EXCLUDED.score,
                last_event_ts   = EXCLUDED.last_event_ts,
                infractions     = EXCLUDED.infractions,
                punishments     = EXCLUDED.punishments,
                blacklisted     = EXCLUDED.blacklisted,
                recent_messages = EXCLUDED.recent_messages,
                updated_at      = NOW()
            """,
            rows,
        )

    async def _flush_whitelists(self, conn) -> None:
        if not self._dirty_whitelist:
            return
        for gid in self._dirty_whitelist:
            wl_strs = self._cache.get(str(gid), {}).get("whitelist", [])
            current_uids = []
            for u in wl_strs:
                try:
                    current_uids.append(int(u))
                except (TypeError, ValueError):
                    continue

            existing = {
                r["user_id"]
                for r in await conn.fetch(
                    "SELECT user_id FROM antispam_whitelist WHERE guild_id = $1",
                    gid,
                )
            }
            target = set(current_uids)
            to_add = target - existing
            to_remove = existing - target

            if to_remove:
                await conn.executemany(
                    "DELETE FROM antispam_whitelist WHERE guild_id = $1 AND user_id = $2",
                    [(gid, uid) for uid in to_remove],
                )
            if to_add:
                await conn.executemany(
                    "INSERT INTO antispam_whitelist (guild_id, user_id) VALUES ($1, $2) "
                    "ON CONFLICT DO NOTHING",
                    [(gid, uid) for uid in to_add],
                )

    async def guild(self, guild_id: int) -> Dict[str, Any]:
        async with self._lock:
            g = await self._load_guild(guild_id)
            # Conservativo: callers podem mutar whitelist via setdefault/append.
            self._dirty_whitelist.add(guild_id)
            return g

    async def user(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        async with self._lock:
            g = await self._load_guild(guild_id)
            uid = str(user_id)
            users = g.setdefault("users", {})
            if uid not in users:
                users[uid] = self._default_user_state()
            self._dirty_users.add((guild_id, user_id))
            return users[uid]
