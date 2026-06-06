"""Lightweight keyword-based category detector for confessions."""
from __future__ import annotations

import re

CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("relationships", "❤️ Relationships", [
        "boyfriend", "girlfriend", "crush", "dating", "love", "relationship",
        "ex ", "breakup", "broke up", "kissed", "marriage", "wife", "husband",
        "partner", "tinder", "bumble",
    ]),
    ("school", "🎓 School", [
        "school", "class", "lecture", "lectures", "exam", "exams", "professor",
        "teacher", "homework", "assignment", "college", "university", "semester",
        "grade", "gpa", "midterm", "thesis",
    ]),
    ("work", "💼 Work", [
        "boss", "manager", "office", "coworker", "co-worker", "colleague",
        "salary", "fired", "promotion", "job", "interview", "client",
        "deadline", "meeting", "wfh",
    ]),
    ("family", "👨‍👩‍👧 Family", [
        "mom", "mum", "mother", "dad", "father", "sister", "brother",
        "parents", "family", "uncle", "aunt", "cousin", "grandma", "grandpa",
    ]),
    ("embarrassing", "😅 Embarrassing", [
        "embarrass", "embarrassed", "embarrassing", "cringe", "awkward",
        "humiliated", "blushed",
    ]),
    ("funny", "😂 Funny", [
        "lol", "lmao", "funny", "hilarious", "joke", "prank",
    ]),
    ("emotional", "😢 Emotional", [
        "cry", "cried", "crying", "depressed", "sad", "lonely", "anxious",
        "anxiety", "hurt", "broken", "miss ", "grief", "loss",
    ]),
]

DEFAULT_CATEGORY = "🤯 Confession"


def detect_category(text: str) -> str:
    if not text:
        return DEFAULT_CATEGORY
    lowered = f" {text.lower()} "
    # Score each category by number of keyword hits to pick the strongest match.
    best_label = DEFAULT_CATEGORY
    best_score = 0
    for _key, label, words in CATEGORIES:
        score = 0
        for w in words:
            pattern = re.escape(w.strip())
            if w.endswith(" "):
                # Whole-word-ish match for short tokens like "ex "
                if re.search(rf"\b{pattern}", lowered):
                    score += 1
            else:
                if pattern in lowered:
                    score += 1
        if score > best_score:
            best_score = score
            best_label = label
    return best_label
