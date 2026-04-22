"""Zero-shot LLM baseline: a single call per chunk with only the 8-category list."""
from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, Field

from .. import config
from ..schemas import Chunk
from ..utils import call_llm, logger, render


class _Flag(BaseModel):
    category: str = ""
    span_text: str = ""
    confidence: float = 0.5
    justification: str = ""


class _Resp(BaseModel):
    flags: list[_Flag] = Field(default_factory=list)


def detect(chunks: Iterable[Chunk]) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        try:
            r, _ = call_llm(
                model=config.ADJUDICATION_MODEL,
                prompt=render("zero_shot_baseline.txt", CHUNK_TEXT=c.text),
                stage="zero_shot_baseline",
                response_schema=_Resp,
            )
        except Exception as e:
            logger.warning("zero-shot baseline failed chunk=%s: %s", c.id, e)
            continue
        for f in r.flags:
            if f.category not in config.ENABLED_CATEGORIES:
                continue
            idx = c.text.find(f.span_text)
            out.append({
                "category": f.category,
                "chunk_id": c.id,
                "span_text": f.span_text,
                "span_char_start": idx if idx >= 0 else 0,
                "span_char_end": (idx + len(f.span_text)) if idx >= 0 else len(f.span_text),
                "confidence": f.confidence,
                "justification": f.justification,
            })
    return out
