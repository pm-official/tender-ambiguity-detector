"""Stage 3 — standards-grounded rewrite with grounding verification (G4).

Prompt-4 update:
- Grounding block now labels TENDER-PACKAGE CONTEXT vs STANDARDS CONTEXT.
- Rewrite runs only for Confirmed Ambiguous (and optionally Partially Resolved) flags.
- Citation regex extended to accept both IS-code and CPWD section references.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from . import config, explain
from .embeddings import VectorStore
from .schemas import DualScoredFlag, FlagCluster, RetrievedContext, Resolution, Rewrite
from .utils import call_llm, logger, render

# Matches: IS 456, IS-456, IS:456, IS 456:2000, IS 1343 Part 1, CPWD Section 3.2, CPWD Sec 3.2, CPWD 2019 Section 4
STANDARDS_REF_RE = re.compile(
    r"\b(?:IS\s*[-:]?\s*\d{2,5}(?:\s*[-:]\s*\d{1,4})?(?:\s*(?:Part|Pt)\s*\d+)?"
    r"|CPWD(?:\s+\d{4})?\s*(?:Section|Sec|Sect|Chap(?:ter)?)\.?\s*\d+(?:\.\d+)*)",
    re.IGNORECASE,
)


class _RewriteResp(BaseModel):
    status: str = "INSUFFICIENT_GROUNDING"
    suggested_text: str = ""
    grounding: list[str] = Field(default_factory=list)
    explanation: str = ""


def _normalise(ref: str) -> str:
    return re.sub(r"\s+", "", ref.upper().replace("IS-", "IS").replace("IS:", "IS"))


def _all_refs(texts: list[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        for m in STANDARDS_REF_RE.finditer(t or ""):
            out.add(_normalise(m.group(0)))
    return out


def _block(label: str, contexts: list[RetrievedContext]) -> str:
    if not contexts:
        return f"--- {label} ---\n(none retrieved)\n"
    lines = [f"--- {label} ---"]
    for c in contexts:
        lines.append(f"[id={c.context_id}] {c.text[:800]}")
    return "\n".join(lines)


def rewrite(
    flag,
    chunk_text: str,
    resolution: Resolution,
    *,
    standards_contexts: list[RetrievedContext] | None = None,
    disable_ground_verify: bool = False,
) -> Optional[Rewrite]:
    # Skip rewrite if the flag was Resolved by Context
    if resolution.verdict in ("RESOLVED_BY_CONTEXT", "RESOLVED"):
        return None

    # Prepare grounding blocks
    tender_ctx = [c for c in resolution.retrieved if c.context_id in resolution.cited_context_ids]
    if not tender_ctx:
        tender_ctx = list(resolution.retrieved)
    stds = standards_contexts or []

    flag_id = getattr(flag, "id", None) or ""
    category = getattr(flag, "category", "F")
    span_text = getattr(flag, "span_text", "")

    prompt = render(
        "rewrite_standards.txt",
        CATEGORY_DISPLAY_NAME=explain.category_display(category),
        SPAN_TEXT=span_text,
        CHUNK_TEXT=chunk_text,
        TENDER_CONTEXT_BLOCK=_block("TENDER-PACKAGE CONTEXT (not authoritative for citations)", tender_ctx),
        STANDARDS_CONTEXT_BLOCK=_block("STANDARDS CONTEXT (authoritative for IS/CPWD citations)", stds),
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
        logger.warning("rewrite failed flag=%s: %s", flag_id, e)
        return Rewrite(
            flag_id=flag_id,
            status="INSUFFICIENT_GROUNDING",
            explanation=f"rewrite failed: {e}",
            stage="standards_grounded",
        )

    status = rw.status if rw.status in ("OK", "INSUFFICIENT_GROUNDING") else "INSUFFICIENT_GROUNDING"
    suggested = rw.suggested_text or ""
    grounding = list(rw.grounding or [])
    explanation_ = rw.explanation or ""

    # G4 — grounding verification (covers IS + CPWD refs)
    if not disable_ground_verify and status == "OK":
        allowed = _all_refs([c.text for c in stds] + grounding)
        used = {_normalise(m.group(0)) for m in STANDARDS_REF_RE.finditer(suggested)}
        fabricated = used - allowed
        if fabricated:
            def _strip(m):
                return "" if _normalise(m.group(0)) in fabricated else m.group(0)
            suggested = STANDARDS_REF_RE.sub(_strip, suggested)
            if not (used - fabricated):
                status = "INSUFFICIENT_GROUNDING"
                suggested = ""
                explanation_ = (
                    f"Rewrite cited refs {sorted(fabricated)} not in STANDARDS block → stripped and downgraded."
                )

    return Rewrite(
        flag_id=flag_id,
        status=status,  # type: ignore[arg-type]
        suggested_text=suggested,
        grounding=grounding,
        explanation=explanation_,
        stage="standards_grounded",
    )


# Backwards-compat shim: old single-argument signature (flag, chunk_text, resolution)
def rewrite_legacy(flag: FlagCluster, chunk_text: str, resolution: Resolution, **kwargs):
    return rewrite(flag, chunk_text, resolution, **kwargs)
