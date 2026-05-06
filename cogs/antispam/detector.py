from __future__ import annotations

import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

import discord

from .config import AntispamConfig
from .normalizer import (
    caps_ratio,
    emoji_count,
    normalize,
    strip_invisible,
)


@dataclass
class Violation:
    kind: str
    score: int
    detail: str = ""


class Detector:
    def __init__(self, config: AntispamConfig):
        self.config = config
        self._link_re = re.compile(config.suspicious_link_pattern, re.IGNORECASE)
        self._url_re = re.compile(r"https?://\S+", re.IGNORECASE)

    def analyze(
        self,
        message: discord.Message,
        user_state: dict,
        edited: bool = False,
    ) -> list[Violation]:
        violations: list[Violation] = []
        cfg = self.config
        scores = cfg.scores
        now = time.time()

        raw = message.content or ""
        clean, removed = strip_invisible(raw)
        norm = normalize(raw)

        recent: list[dict] = user_state.setdefault("recent_messages", [])
        cutoff = now - max(cfg.flood_window_s * 4, 30.0)
        recent[:] = [r for r in recent if r["ts"] >= cutoff]

        recent_in_window = [r for r in recent if r["ts"] >= now - cfg.flood_window_s]
        if len(recent_in_window) + 1 > cfg.flood_max_msgs:
            violations.append(Violation(
                "flood",
                scores["flood"],
                f"{len(recent_in_window) + 1} msgs/{cfg.flood_window_s:g}s",
            ))

        if norm:
            for r in recent[-cfg.similarity_window:]:
                prev = r.get("norm", "")
                if not prev:
                    continue
                ratio = SequenceMatcher(None, prev, norm).ratio()
                if ratio >= cfg.similarity_threshold:
                    violations.append(Violation(
                        "duplicate",
                        scores["duplicate"],
                        f"sim={ratio:.2f}",
                    ))
                    break

        mentions = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone:
            mentions += 5
        if mentions >= cfg.mention_hard:
            violations.append(Violation("mention_hard", scores["mention_hard"], f"{mentions} mentions"))
        elif mentions >= cfg.mention_soft:
            violations.append(Violation("mention_soft", scores["mention_soft"], f"{mentions} mentions"))

        urls = self._url_re.findall(clean)
        if urls:
            for url in urls:
                if self._link_re.search(url):
                    violations.append(Violation(
                        "suspicious_link",
                        scores["suspicious_link"],
                        url[:80],
                    ))
                    break
            if len(urls) >= 4:
                violations.append(Violation(
                    "suspicious_link",
                    scores["suspicious_link"],
                    f"{len(urls)} urls",
                ))

        low = norm
        for kw in cfg.phishing_keywords:
            if kw in low:
                violations.append(Violation("phishing", scores["phishing"], kw))
                break

        for kw in cfg.promo_keywords:
            if kw in low:
                violations.append(Violation("promo_spam", scores["promo_spam"], kw))
                break

        has_url = bool(urls)
        for phrase in cfg.link_bait_phrases:
            if phrase in low and has_url:
                violations.append(Violation("link_bait", scores["link_bait"], f'"{phrase}" + url'))
                break

        if removed >= 3:
            violations.append(Violation(
                "invisible_chars",
                scores["invisible_chars"],
                f"{removed} zero-width",
            ))

        if len(clean) >= cfg.caps_min_len and caps_ratio(clean) >= cfg.caps_ratio:
            violations.append(Violation("caps", scores["caps"]))

        if emoji_count(clean) > cfg.emoji_max:
            violations.append(Violation("emoji_flood", scores["emoji_flood"]))

        if clean.count("\n") > cfg.newline_max:
            violations.append(Violation("newline_flood", scores["newline_flood"]))

        if edited and norm:
            violations.append(Violation("edit_spam", scores["edit_spam"]))

        recent.append({"ts": now, "norm": norm, "len": len(clean)})
        if len(recent) > 30:
            del recent[: len(recent) - 30]

        return violations

    @staticmethod
    def total_score(violations: Iterable[Violation]) -> int:
        return sum(v.score for v in violations)
