from __future__ import annotations

from dataclasses import dataclass, field


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
