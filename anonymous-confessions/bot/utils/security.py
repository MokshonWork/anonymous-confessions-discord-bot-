"""Security helpers: profanity filter, duplicate detection, content hashing."""
from __future__ import annotations

import hashlib
import re

from better_profanity import profanity

profanity.load_censor_words()

# Very high-level slur/extreme-content blocklist. Anything matching is hard-blocked.
HARD_BLOCK_PATTERNS = [
    # Self-harm encouragement
    r"\bkill\s+yourself\b",
    r"\bkys\b",
    # Doxxing-style markers
    r"\bhome\s+address\b",
    r"\bphone\s+number\s+is\b",
]
_HARD_BLOCK_RE = re.compile("|".join(HARD_BLOCK_PATTERNS), re.IGNORECASE)


def is_hard_blocked(text: str) -> bool:
    return bool(_HARD_BLOCK_RE.search(text or ""))


def contains_profanity(text: str) -> bool:
    return profanity.contains_profanity(text or "")


def censor(text: str) -> str:
    return profanity.censor(text or "")


def content_hash(text: str) -> str:
    """Stable hash used for duplicate detection (normalises whitespace + case)."""
    normalised = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
