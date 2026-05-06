from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import Any


class JSONStorage:
    def __init__(self, path: str):
        self.path = path
        self._lock = asyncio.Lock()
        self._cache: dict[str, Any] | None = None

    async def load(self) -> dict[str, Any]:
        async with self._lock:
            if self._cache is not None:
                return self._cache
            self._cache = await asyncio.to_thread(self._read)
            return self._cache

    def _read(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            return {"guilds": {}, "config": {}}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"guilds": {}, "config": {}}

    async def save(self) -> None:
        async with self._lock:
            if self._cache is None:
                return
            await asyncio.to_thread(self._write, self._cache)

    def _write(self, data: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".antispam.", dir=os.path.dirname(self.path) or ".")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    async def guild(self, guild_id: int) -> dict[str, Any]:
        data = await self.load()
        gid = str(guild_id)
        guilds = data.setdefault("guilds", {})
        if gid not in guilds:
            guilds[gid] = {
                "users": {},
                "whitelist": [],
                "config_overrides": {},
            }
        return guilds[gid]

    async def user(self, guild_id: int, user_id: int) -> dict[str, Any]:
        g = await self.guild(guild_id)
        uid = str(user_id)
        users = g.setdefault("users", {})
        if uid not in users:
            users[uid] = {
                "score": 0.0,
                "last_event_ts": 0.0,
                "infractions": [],
                "punishments": [],
                "blacklisted": False,
                "recent_messages": [],
            }
        return users[uid]
