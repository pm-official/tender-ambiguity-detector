"""Simple keyword/regex baseline. Reference lower bound (no IS-code content — just vague-word lists)."""
from __future__ import annotations

import re
from typing import Iterable

from ..schemas import Chunk

KEYWORDS = {
    "F": [r"\bsuitable\b", r"\bapproved\b", r"\bstandard\b", r"\bproper\b"],
    "B": [r"\badequate\b", r"\breasonable\b", r"\bsufficient\b", r"\bgood quality\b", r"\bsatisfactory\b"],
    "I": [r"\bas per (the )?relevant\b", r"\brefer to (the )?(attached|relevant)\b", r"\bper the schedule\b"],
    "A": [r"\bfair\b", r"\baccess\b", r"\bblock\b", r"\blevel\b"],
    "E": [r"\b(They|He|She|It) shall\b"],
    "J": [r"\bapply (the )?primer\b", r"\bseal .* joints\b", r"\bwaterproofing\b"],
}


def detect(chunks: Iterable[Chunk]) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        for cat, patterns in KEYWORDS.items():
            for pat in patterns:
                for m in re.finditer(pat, c.text, re.IGNORECASE):
                    out.append({
                        "category": cat,
                        "chunk_id": c.id,
                        "span_text": m.group(0),
                        "span_char_start": m.start(),
                        "span_char_end": m.end(),
                        "confidence": 0.5,
                    })
    return out
