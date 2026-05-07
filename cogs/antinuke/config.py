from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class AntinukeConfig:
    enabled: bool = True

    # Quando True: só alerta, nunca age automaticamente
    alert_only: bool = True

    # Thresholds: (contagem, janela_em_segundos)
    join_rate: tuple[int, float] = (15, 30.0)
    channel_delete_rate: tuple[int, float] = (3, 10.0)
    role_delete_rate: tuple[int, float] = (3, 10.0)
    ban_rate: tuple[int, float] = (5, 10.0)
    kick_rate: tuple[int, float] = (5, 10.0)
    mass_mention_rate: tuple[int, float] = (10, 15.0)  # cross-channel/user

    # Conta criada há menos de N dias → flagged no join
    min_account_age_days: int = 7

    # Lockdown automático: duração em minutos antes de auto-unlock
    lockdown_duration_minutes: int = 10

    # Escala de severidade: quantos alertas acumulados antes de escalar ação
    # severity 1 → log | 2 → ping admins | 3 → slowmode | 4 → lockdown
    severity_thresholds: dict[int, str] = field(default_factory=lambda: {
        1: "log",
        2: "ping",
        3: "slowmode",
        4: "lockdown",
    })

    log_channel_id: int | None = None
    admin_ping_ids: list[int] = field(default_factory=list)
    whitelist_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Tuplas viram listas no JSONB; preservamos a serialização canônica
        for k in ("join_rate", "channel_delete_rate", "role_delete_rate",
                  "ban_rate", "kick_rate", "mass_mention_rate"):
            v = d.get(k)
            if isinstance(v, tuple):
                d[k] = list(v)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AntinukeConfig":
        defaults = asdict(cls())
        merged = {**defaults, **(data or {})}
        # Reconstroi tuplas (rates) e dict[int, str] (severity)
        for k in ("join_rate", "channel_delete_rate", "role_delete_rate",
                  "ban_rate", "kick_rate", "mass_mention_rate"):
            v = merged.get(k)
            if isinstance(v, list) and len(v) == 2:
                merged[k] = (int(v[0]), float(v[1]))
        if isinstance(merged.get("severity_thresholds"), dict):
            merged["severity_thresholds"] = {
                int(k): v for k, v in merged["severity_thresholds"].items()
            }
        valid = set(defaults.keys())
        merged = {k: v for k, v in merged.items() if k in valid}
        return cls(**merged)

    @classmethod
    async def load_from_db(cls, pool, guild_id: int) -> "AntinukeConfig":
        if pool is None:
            return cls()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT config, enabled, alert_only FROM antinuke_config "
                    "WHERE guild_id = $1",
                    guild_id,
                )
        except Exception:
            return cls()
        if row is None:
            return cls()
        cfg = cls.from_dict(row["config"] or {})
        if row["enabled"] is False:
            cfg.enabled = False
        if row["alert_only"] is not None:
            cfg.alert_only = bool(row["alert_only"])
        return cfg

    async def save_to_db(self, pool, guild_id: int) -> None:
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO antinuke_config (guild_id, config, enabled, alert_only, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (guild_id) DO UPDATE SET
                    config     = EXCLUDED.config,
                    enabled    = EXCLUDED.enabled,
                    alert_only = EXCLUDED.alert_only,
                    updated_at = NOW()
                """,
                guild_id,
                self.to_dict(),
                self.enabled,
                self.alert_only,
            )
