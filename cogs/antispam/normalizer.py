from __future__ import annotations

import re
import unicodedata

ZERO_WIDTH = {
    "​", "‌", "‍", "‎", "‏",
    "‪", "‫", "‬", "‭", "‮",
    "⁠", "⁡", "⁢", "⁣", "⁤",
    "﻿",
}

_CONFUSABLES = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s", "!": "i",
})

_REPEAT = re.compile(r"(.)\1{2,}")
_SPACES = re.compile(r"\s+")


def strip_invisible(text: str) -> tuple[str, int]:
    removed = 0
    out = []
    for ch in text:
        if ch in ZERO_WIDTH:
            removed += 1
            continue
        out.append(ch)
    return "".join(out), removed


def normalize(text: str) -> str:
    text, _ = strip_invisible(text)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(_CONFUSABLES)
    text = _REPEAT.sub(r"\1\1", text)
    text = _SPACES.sub(" ", text).strip()
    return text


def caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters)


def emoji_count(text: str) -> int:
    custom = len(re.findall(r"<a?:\w+:\d+>", text))
    unicode_emoji = sum(1 for c in text if unicodedata.category(c) == "So")
    return custom + unicode_emoji
