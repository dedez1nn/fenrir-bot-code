from __future__ import annotations

import time
from collections import defaultdict


class SlidingWindow:
    """
    Contador de eventos por chave com janela deslizante.
    Chave típica: f"{guild_id}:{event_type}" ou f"{guild_id}:{user_id}:{event_type}"
    """

    def __init__(self):
        self._events: dict[str, list[float]] = defaultdict(list)

    def record(self, key: str, now: float | None = None) -> int:
        now = now or time.time()
        self._events[key].append(now)
        return len(self._events[key])

    def count(self, key: str, window: float, now: float | None = None) -> int:
        now = now or time.time()
        cutoff = now - window
        events = self._events.get(key)
        if not events:
            return 0
        trimmed = [t for t in events if t >= cutoff]
        self._events[key] = trimmed
        return len(trimmed)

    def record_and_count(self, key: str, window: float, now: float | None = None) -> int:
        now = now or time.time()
        self.record(key, now)
        return self.count(key, window, now)

    def clear(self, key: str) -> None:
        self._events.pop(key, None)

    def clear_guild(self, guild_id: int) -> None:
        prefix = f"{guild_id}:"
        for k in list(self._events.keys()):
            if k.startswith(prefix):
                del self._events[k]


class ServerSeverity:
    """
    Severidade acumulada por servidor, com decaimento por tempo.
    Cada alerta gerado adiciona +1. Decai 1 por minuto sem novos eventos.
    """

    def __init__(self):
        self._severity: dict[int, float] = {}
        self._last_ts: dict[int, float] = {}

    def current(self, guild_id: int) -> int:
        self._decay(guild_id)
        return int(self._severity.get(guild_id, 0))

    def increment(self, guild_id: int, delta: int = 1) -> int:
        self._decay(guild_id)
        now = time.time()
        self._severity[guild_id] = self._severity.get(guild_id, 0) + delta
        self._last_ts[guild_id] = now
        return int(self._severity[guild_id])

    def reset(self, guild_id: int) -> None:
        self._severity[guild_id] = 0
        self._last_ts[guild_id] = time.time()

    def _decay(self, guild_id: int) -> None:
        last = self._last_ts.get(guild_id)
        sev = self._severity.get(guild_id, 0)
        if last and sev > 0:
            elapsed_min = (time.time() - last) / 60.0
            self._severity[guild_id] = max(0.0, sev - elapsed_min)
