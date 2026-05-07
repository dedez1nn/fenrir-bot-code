from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict


@dataclass
class AntispamConfig:
    flood_window_s: float = 5.0
    flood_max_msgs: int = 5

    similarity_window: int = 6
    similarity_threshold: float = 0.92

    mention_soft: int = 5
    mention_hard: int = 10

    caps_min_len: int = 20
    caps_ratio: float = 0.7

    emoji_max: int = 10
    newline_max: int = 10

    enabled: bool = True

    decay_per_minute: float = 1.0

    scores: Dict[str, int] = field(default_factory=lambda: {
        "flood": 3,
        "duplicate": 4,
        "mention_soft": 5,
        "mention_hard": 8,
        "suspicious_link": 3,
        "phishing": 6,
        "invisible_chars": 2,
        "caps": 1,
        "emoji_flood": 1,
        "newline_flood": 2,
        "edit_spam": 2,
        "external_invite": 2,
        "promo_spam": 4,
        "link_bait": 5,
        "suspicious_email": 3,
    })

    ladder: Dict[int, str] = field(default_factory=lambda: {
        5: "warn",
        10: "timeout_5",
        20: "timeout_10",
        35: "kick",
        50: "ban",
    })

    blacklist_apply_score: int = 25
    blacklist_remove_score: int = 8
    blacklist_role_name: str = "Blacklist"

    log_channel_id: int | None = None

    suspicious_link_pattern: str = (
        r"(bit\.ly|tinyurl\.com|goo\.gl|t\.co|cutt\.ly|is\.gd|"
        r"shorte\.st|adf\.ly|ow\.ly|rebrand\.ly|grabify\.link|iplogger)"
    )
    phishing_keywords: list[str] = field(default_factory=lambda: [
        "free nitro", "nitro free", "free discord nitro", "steam gift",
        "csgo skin free", "free skins", "click here to claim",
        "discord-nitro", "discordapp.gift", "stearncommunity",
        "stearnpowered", "discrod.com", "dlscord.com", "diiscord",
    ])

    # Frases promocionais/publicitárias — dispara mesmo sem link
    promo_keywords: list[str] = field(default_factory=lambda: [
        "veja minha promoção", "confira minha promoção", "minha promoção",
        "acesse meu canal", "segue meu canal", "inscreva-se no meu canal",
        "se inscreve no meu", "segue meu perfil", "me segue lá",
        "oferta exclusiva", "oportunidade única", "não perca essa oferta",
        "ganhe dinheiro", "renda extra", "trabalhe de casa",
        "compre agora", "compra agora", "adquira agora",
        "acesse minha loja", "minha loja online", "loja oficial",
        "produto exclusivo", "desconto imperdivel", "desconto imperdível",
        "aproveite a promoção", "últimas unidades", "estoque limitado",
    ])

    # Frases de iscagem de clique — só dispara quando acompanhadas de URL
    link_bait_phrases: list[str] = field(default_factory=lambda: [
        "olha esse link", "veja esse link", "confere esse link",
        "clica aqui", "clique aqui", "acessa aqui", "acesse aqui",
        "entra aqui", "entra nesse link", "entra no link",
        "veja mais em", "saiba mais em", "confira em",
        "acesse:", "link:", "site:", "acesse agora",
        "corre ver", "vai lá ver", "da uma olhada aqui",
        "olha só:", "olha aqui:", "confira:", "veja:",
    ])

    def threshold_for(self, score: int) -> str | None:
        action = None
        for need in sorted(self.ladder.keys()):
            if score >= need:
                action = self.ladder[need]
        return action

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AntispamConfig":
        defaults = asdict(cls())
        merged = {**defaults, **(data or {})}
        if "ladder" in merged and isinstance(merged["ladder"], dict):
            merged["ladder"] = {int(k): v for k, v in merged["ladder"].items()}
        valid = set(defaults.keys())
        merged = {k: v for k, v in merged.items() if k in valid}
        return cls(**merged)

    @classmethod
    async def load_from_db(cls, pool, guild_id: int) -> "AntispamConfig":
        """Carrega config da tabela `antispam_config`. Fallback para defaults."""
        if pool is None:
            return cls()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT config, enabled FROM antispam_config WHERE guild_id = $1",
                    guild_id,
                )
        except Exception:
            return cls()
        if row is None:
            return cls()
        cfg = cls.from_dict(row["config"] or {})
        if row["enabled"] is False:
            cfg.enabled = False
        return cfg

    async def save_to_db(self, pool, guild_id: int) -> None:
        """Persiste config como JSONB. Idempotente."""
        if pool is None:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO antispam_config (guild_id, config, enabled, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (guild_id) DO UPDATE SET
                    config     = EXCLUDED.config,
                    enabled    = EXCLUDED.enabled,
                    updated_at = NOW()
                """,
                guild_id,
                self.to_dict(),
                self.enabled,
            )
