from __future__ import annotations

import time

from .config import AntispamConfig
from .storage import JSONStorage


class ScoreManager:
    def __init__(self, storage: JSONStorage, config: AntispamConfig):
        self.storage = storage
        self.config = config

    def _decay(self, user_state: dict, now: float) -> float:
        last = float(user_state.get("last_event_ts") or 0.0)
        score = float(user_state.get("score") or 0.0)
        if last <= 0 or score <= 0:
            user_state["score"] = max(0.0, score)
            user_state["last_event_ts"] = now
            return user_state["score"]
        elapsed_min = max(0.0, (now - last) / 60.0)
        decayed = max(0.0, score - elapsed_min * self.config.decay_per_minute)
        user_state["score"] = decayed
        user_state["last_event_ts"] = now
        return decayed

    async def current_score(self, guild_id: int, user_id: int) -> float:
        user_state = await self.storage.user(guild_id, user_id)
        return self._decay(user_state, time.time())

    async def add(
        self,
        guild_id: int,
        user_id: int,
        delta: int,
        reason: str,
        evidence: dict | None = None,
    ) -> float:
        user_state = await self.storage.user(guild_id, user_id)
        now = time.time()
        decayed = self._decay(user_state, now)
        new_score = decayed + delta
        user_state["score"] = new_score
        user_state["infractions"].append({
            "ts": now,
            "delta": delta,
            "reason": reason,
            "evidence": evidence or {},
        })
        if len(user_state["infractions"]) > 100:
            user_state["infractions"] = user_state["infractions"][-100:]
        await self.storage.save()
        return new_score

    async def reset(self, guild_id: int, user_id: int) -> None:
        user_state = await self.storage.user(guild_id, user_id)
        user_state["score"] = 0.0
        user_state["infractions"] = []
        user_state["last_event_ts"] = time.time()
        await self.storage.save()

    async def record_punishment(
        self,
        guild_id: int,
        user_id: int,
        action: str,
        reason: str,
    ) -> None:
        user_state = await self.storage.user(guild_id, user_id)
        user_state["punishments"].append({
            "ts": time.time(),
            "action": action,
            "reason": reason,
        })
        if len(user_state["punishments"]) > 50:
            user_state["punishments"] = user_state["punishments"][-50:]
        await self.storage.save()
