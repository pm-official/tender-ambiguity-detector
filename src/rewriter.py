"""IS-code-grounded rewriter with grounding verification (G4)."""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from . import config
from .schemas import FlagCluster, RetrievedContext, Resolution, Rewrite
from .utils import call_llm, logger, render

IS_REF_RE = re.compile(r"\bIS\s*[-:]?\s*\d{2,5}(?:\s*[-:]\s*\d{1,4})?(?:\s*(?:Part|Pt)\s*\d+)?", re.IGNORECASE)


class _RewriteResp(BaseModel):
    status: str = "INSUFFICIENT_GROUNDING"
    suggested_text: str = ""
    grounding: list[str] = Field(default_factory=list)
    explanation: str = ""


def _grounding_block(contexts: list[RetrievedContext]) -> str:
    if not contexts:
        return "(no grounding retrieved)"
    return "\n\n".join(f"[id={c.context_id}] {c.text[:800]}" for c in contexts)


def _all_is_refs(texts: list[str]) -> set[str]:
    refs: set[str] = set()
    for t in texts:
        for m in IS_REF_RE.finditer(t):
            refs.add(_normalize_ref(m.group(0)))
    return refs


def _normalize_ref(ref: str) -> str:
    return re.sub(r"\s+", "", ref.upper().replace("IS-", "IS").replace("IS:", "IS"))


def rewrite(
    flag: FlagCluster,
    chunk_text: str,
    resolution: Resolution,
    *,
    disable_ground_verify: bool = False,
) -> Optional[Rewrite]:
    if resolution.verdict == "RESOLVED":
        return None  # nothing to rewrite

    cited = [c for c in resolution.retrieved if c.context_id in resolution.cited_context_ids]
    grounding_contexts = cited if cited else resolution.retrieved

    prompt = render(
        "rewrite.txt",
        CATEGORY=flag.category,
        CATEGORY_NAME=config.CATEGORY_NAMES[flag.category],
        SPAN_TEXT=flag.span_text,
        CHUNK_TEXT=chunk_text,
        GROUNDING_BLOCK=_grounding_block(grounding_contexts),
    )
    try:
        rw, _ = call_llm(
            model=config.REWRITE_MODEL,
            prompt=prompt,
            stage="rewrite",
            response_schema=_RewriteResp,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("rewrite failed flag=%s: %s", flag.id, e)
        return Rewrite(flag_id=flag.id, status="INSUFFICIENT_GROUNDING", explanation=f"rewrite failed: {e}")

    status = rw.status if rw.status in ("OK", "INSUFFICIENT_GROUNDING") else "INSUFFICIENT_GROUNDING"
    suggested = rw.suggested_text or ""
    grounding = list(rw.grounding or [])
    explanation = rw.explanation or ""

    # G4 — grounding verification
    if not disable_ground_verify and status == "OK":
        allowed_refs = _all_is_refs([c.text for c in grounding_contexts] + grounding)
        used_refs = set(_normalize_ref(m.group(0)) for m in IS_REF_RE.finditer(suggested))
        fabricated = used_refs - allowed_refs
        if fabricated:
            # Strip fabricated references from text
            def _strip(m):
                norm = _normalize_ref(m.group(0))
                return "" if norm in fabricated else m.group(0)
            suggested = IS_REF_RE.sub(_strip, suggested)
            # If nothing defensible remains
            if not (used_refs - fabricated):
                status = "INSUFFICIENT_GROUNDING"
                suggested = ""
                explanation = f"Rewrite cited IS-code refs {sorted(fabricated)} not in grounding → stripped and downgraded."

    return Rewrite(
        flag_id=flag.id,
        status=status,  # type: ignore[arg-type]
        suggested_text=suggested,
        grounding=grounding,
        explanation=explanation,
    )
