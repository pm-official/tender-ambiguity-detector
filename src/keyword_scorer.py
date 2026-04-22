"""Lexicon-based keyword scorer for Stage-1 dual scoring.

Every category has its own YAML lexicon under data/keywords/{category_id}.yaml.
Entries: [{term, weight, requires_context?, forbid_context?}]
"""
from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Optional

import yaml

from .schemas import Chunk, KeywordMatch

LEX_DIR = Path(__file__).resolve().parent.parent / "data" / "keywords"


def _token_count(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))


@functools.lru_cache(maxsize=64)
def load_lexicon(category_id: str) -> list[dict]:
    path = LEX_DIR / f"{category_id}.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("entries", []) if isinstance(data, dict) else data
    out: list[dict] = []
    for raw in entries or []:
        if isinstance(raw, str):
            out.append({"term": raw, "weight": 0.5})
        elif isinstance(raw, dict) and raw.get("term"):
            entry = {"term": str(raw["term"]), "weight": float(raw.get("weight", 0.5))}
            if raw.get("requires_context"):
                entry["requires_context"] = str(raw["requires_context"])
            if raw.get("forbid_context"):
                entry["forbid_context"] = str(raw["forbid_context"])
            out.append(entry)
    return out


def _context_after(text: str, end: int, window: int = 30) -> str:
    return text[end : end + window]


def _passes_context_rules(entry: dict, text: str, match_start: int, match_end: int) -> tuple[bool, Optional[str]]:
    """Return (ok, rule_triggered_name). Very light heuristics — no spaCy dep."""
    after = _context_after(text, match_end, 40).strip()
    requires = entry.get("requires_context")
    forbid = entry.get("forbid_context")
    rule_name = None
    if requires == "noun":
        # crude: next token is a word of length >=3 and not an article/preposition
        first = after.split()[0] if after else ""
        if not re.match(r"^[A-Za-z][a-z]{2,}$", first) or first.lower() in {"the", "and", "for", "with", "per", "any", "all"}:
            return False, "requires_noun_after"
        rule_name = "requires_noun_after"
    elif requires == "adj_then_noun":
        # for anaphoric pronouns etc, insist on a verb after
        if not re.match(r"^\s*(shall|will|may|must|is|are|has|have)\b", after, re.IGNORECASE):
            return False, "requires_modal_after"
        rule_name = "requires_modal_after"
    if forbid == "numeric":
        # if the surrounding text contains a number/IS-ref within window, skip
        around = text[max(0, match_start - 40) : match_end + 40]
        if re.search(r"\b\d+\b|\bIS[\s:-]\s*\d+\b", around):
            return False, "forbid_numeric_nearby"
        rule_name = rule_name or "forbid_numeric_nearby"
    return True, rule_name


def score_chunk(chunk: Chunk, category_id: str) -> tuple[float, list[KeywordMatch]]:
    lex = load_lexicon(category_id)
    if not lex:
        return 0.0, []
    text = chunk.text
    matches: list[KeywordMatch] = []
    raw_score = 0.0
    for entry in lex:
        term = entry["term"]
        weight = float(entry.get("weight", 0.5))
        pattern = r"\b" + re.escape(term) + r"\b"
        for m in re.finditer(pattern, text, re.IGNORECASE):
            ok, rule = _passes_context_rules(entry, text, m.start(), m.end())
            if not ok:
                continue
            matches.append(
                KeywordMatch(term=term, weight=weight, position=m.start(), rule_triggered=rule)
            )
            raw_score += weight

    # Normalise by token count / 100, cap at 1.0
    toks = _token_count(text)
    normalised = raw_score / max(1.0, toks / 100.0)
    return min(1.0, normalised), matches
