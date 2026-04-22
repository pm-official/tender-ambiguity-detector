"""Dual-scoring detector (Prompt-4 primary path) + legacy 3-pass ensemble behind a flag.

Default behaviour:
  for each chunk × category:
    keyword_score  <- keyword_scorer.score_chunk(chunk, cat)
    llm_score, span, justification  <- single Gemini Flash call with detection_score_{cat}.txt
    combined = α·keyword + (1-α)·llm
    if combined >= threshold → emit DualScoredFlag
Optional G2 negative probe still available as a post-pass (downgrades confidence on disagreement).

Legacy three-pass ensemble (Prompt-3) is preserved in `detect_legacy_ensemble` and runs when
`config.USE_LEGACY_ENSEMBLE=True` or when the ablation explicitly calls it.
"""
from __future__ import annotations

import json
import uuid
from typing import Iterable

from pydantic import BaseModel, Field

from . import config
from .keyword_scorer import score_chunk as kw_score_chunk
from .schemas import (
    Chunk,
    DetectionPass,
    DualScoredFlag,
    FlagCluster,
    KeywordMatch,
    NegativeProbe,
)
from .utils import active_run_dir, call_llm, iou, logger, render


# ---------------------------------------------------------------------------
# Scoring response schemas
# ---------------------------------------------------------------------------


class _ScoreResp(BaseModel):
    score: float = 0.0
    span_text: str = ""
    span_start: int = 0
    justification: str = ""


class _DetectionItem(BaseModel):
    """Legacy ensemble pass item."""
    span_text: str
    span_char_start: int = 0
    span_char_end: int = 0
    confidence: float = 0.5
    justification: str = ""


class _DetectionResponse(BaseModel):
    flags: list[_DetectionItem] = Field(default_factory=list)


class _ProbeResponse(BaseModel):
    disagrees: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _locate_span(text: str, span_text: str, hint_start: int = 0, hint_end: int = 0) -> tuple[int, int]:
    if not span_text:
        return 0, 0
    if 0 <= hint_start < hint_end <= len(text) and text[hint_start:hint_end].strip() == span_text.strip():
        return hint_start, hint_end
    idx = text.find(span_text)
    if idx >= 0:
        return idx, idx + len(span_text)
    probe = span_text[:20].strip()
    if probe:
        idx = text.find(probe)
        if idx >= 0:
            return idx, idx + len(span_text)
    return 0, 0


def _fallback_span_from_keyword(matches: list[KeywordMatch], chunk_text: str) -> tuple[str, int, int]:
    """If the LLM gave no span but keywords fired, use the highest-weighted keyword as the span."""
    if not matches:
        return "", 0, 0
    top = max(matches, key=lambda m: m.weight)
    s = max(0, int(top.position))
    e = min(len(chunk_text), s + len(top.term))
    return chunk_text[s:e], s, e


# ---------------------------------------------------------------------------
# LLM score (single call)
# ---------------------------------------------------------------------------


def _llm_score(chunk: Chunk, category: str) -> _ScoreResp:
    try:
        prompt = render(f"detection_score_{category}.txt", CHUNK_TEXT=chunk.text)
        resp, _ = call_llm(
            model=config.DETECTION_MODEL,
            prompt=prompt,
            stage=f"detect_score_{category}",
            response_schema=_ScoreResp,
            temperature=0.0,
        )
        # clip
        resp.score = max(0.0, min(1.0, float(resp.score)))
        return resp
    except Exception as e:
        logger.warning("dual-scoring LLM failed cat=%s chunk=%s: %s", category, chunk.id, e)
        return _ScoreResp(score=0.0, span_text="", span_start=0, justification=f"(llm error: {e})")


# ---------------------------------------------------------------------------
# Negative probe (G2)
# ---------------------------------------------------------------------------


def _negative_probe(chunk: Chunk, category: str, span_text: str) -> NegativeProbe | None:
    try:
        prompt = render(
            "negative_probe.txt",
            CATEGORY=category,
            CATEGORY_NAME=config.CATEGORY_NAMES[category],
            SPAN_TEXT=span_text,
            CHUNK_TEXT=chunk.text,
        )
        resp, _ = call_llm(
            model=config.DETECTION_MODEL,
            prompt=prompt,
            stage=f"probe_{category}",
            response_schema=_ProbeResponse,
            temperature=0.0,
        )
        return NegativeProbe(category=category, span_text=span_text, disagrees=resp.disagrees, reason=resp.reason)
    except Exception as e:
        logger.warning("probe failed cat=%s span=%r: %s", category, span_text[:40], e)
        return None


# ---------------------------------------------------------------------------
# Dual-scoring entry point
# ---------------------------------------------------------------------------


def detect_dual(
    chunks: Iterable[Chunk],
    *,
    enabled_categories: list[str] | None = None,
    alpha: float | None = None,
    threshold: float | None = None,
    per_category_thresholds: dict[str, float] | None = None,
    disable_neg_probe: bool = False,
    package_id: str | None = None,
    progress_cb=None,
) -> list[DualScoredFlag]:
    enabled = enabled_categories or config.ENABLED_CATEGORIES
    a = float(alpha) if alpha is not None else float(config.KEYWORD_SCORE_WEIGHT_ALPHA)
    default_thr = float(threshold) if threshold is not None else float(config.DETECTION_THRESHOLD)
    per_cat = per_category_thresholds or {}

    chunks = list(chunks)
    total = len(chunks) * len(enabled)
    step = 0
    flags: list[DualScoredFlag] = []
    rows_log = []

    for chunk in chunks:
        for cat in enabled:
            step += 1
            if progress_cb:
                progress_cb(step, total, f"Score {cat} on {chunk.id}")
            kw_s, kw_matches = kw_score_chunk(chunk, cat)
            llm_r = _llm_score(chunk, cat)
            combined = a * kw_s + (1.0 - a) * llm_r.score

            rows_log.append({
                "chunk_id": chunk.id,
                "category": cat,
                "keyword_score": round(kw_s, 4),
                "llm_score": round(llm_r.score, 4),
                "combined_score": round(combined, 4),
                "kw_matches": len(kw_matches),
            })

            thr = per_cat.get(cat, default_thr)
            if combined < thr:
                continue

            span_text = llm_r.span_text or ""
            s = e = 0
            if span_text:
                s, e = _locate_span(chunk.text, span_text, llm_r.span_start, llm_r.span_start + len(span_text))
            if not span_text or e <= s:
                span_text, s, e = _fallback_span_from_keyword(kw_matches, chunk.text)
            if not span_text:
                # final fallback — first 60 chars of chunk
                span_text = chunk.text[:60]
                s, e = 0, min(60, len(chunk.text))

            flag = DualScoredFlag(
                id=f"ds_{uuid.uuid4().hex[:10]}",
                chunk_id=chunk.id,
                category=cat,
                span_text=span_text,
                span_char_start=s,
                span_char_end=e,
                keyword_score=round(kw_s, 4),
                llm_score=round(llm_r.score, 4),
                combined_score=round(combined, 4),
                keyword_matches=kw_matches,
                justification=llm_r.justification or "",
                package_id=package_id,
                status="CONFIRMED",
            )

            # G2 negative probe on local categories only
            if not disable_neg_probe and cat not in config.GRAPH_CATEGORIES:
                probe = _negative_probe(chunk, cat, flag.span_text)
                if probe and probe.disagrees:
                    flag.combined_score = round(max(0.0, flag.combined_score - 0.2), 4)
                    if flag.combined_score < thr:
                        flag.status = "REVIEW_QUEUE"

            flags.append(flag)

    # Persist a transparency log of every score so the UI can show it.
    try:
        p = active_run_dir() / "dual_scores.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for row in rows_log:
                f.write(json.dumps(row) + "\n")
    except Exception as e:
        logger.warning("failed to write dual_scores log: %s", e)

    return flags


# ---------------------------------------------------------------------------
# Legacy three-pass ensemble (Prompt-3) — preserved for ablation
# ---------------------------------------------------------------------------


def _run_pass(chunk: Chunk, category: str, variant: str) -> list[DetectionPass]:
    suffix = "" if variant == "v1" else f"_{variant}"
    prompt_name = f"detection_{category}{suffix}.txt"
    try:
        prompt = render(prompt_name, CHUNK_TEXT=chunk.text)
        resp, _ = call_llm(
            model=config.DETECTION_MODEL,
            prompt=prompt,
            stage=f"detect_{category}_{variant}",
            response_schema=_DetectionResponse,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("legacy pass failed cat=%s variant=%s: %s", category, variant, e)
        return []

    out: list[DetectionPass] = []
    for item in resp.flags:
        s, ee = _locate_span(chunk.text, item.span_text, item.span_char_start, item.span_char_end)
        if ee <= s:
            continue
        out.append(
            DetectionPass(
                pass_id=variant,
                category=category,
                chunk_id=chunk.id,
                span_text=item.span_text,
                span_char_start=s,
                span_char_end=ee,
                confidence=max(0.0, min(1.0, item.confidence)),
                justification=item.justification,
            )
        )
    return out


def _cluster_passes(passes: list[DetectionPass], iou_thresh: float) -> list[list[DetectionPass]]:
    unassigned = list(passes)
    clusters: list[list[DetectionPass]] = []
    while unassigned:
        seed = unassigned.pop(0)
        group = [seed]
        remaining: list[DetectionPass] = []
        for p in unassigned:
            if iou((seed.span_char_start, seed.span_char_end), (p.span_char_start, p.span_char_end)) >= iou_thresh:
                group.append(p)
            else:
                remaining.append(p)
        clusters.append(group)
        unassigned = remaining
    return clusters


def detect_legacy_ensemble(
    chunks: Iterable[Chunk],
    *,
    enabled_categories: list[str] | None = None,
    agreement_threshold: int | None = None,
    confidence_thresholds: dict[str, float] | None = None,
    disable_neg_probe: bool = False,
    progress_cb=None,
) -> list[FlagCluster]:
    enabled = enabled_categories or config.ENABLED_CATEGORIES
    thr = agreement_threshold if agreement_threshold is not None else config.DETECTION_AGREEMENT_THRESHOLD
    confs = confidence_thresholds or config.DETECTION_CONFIDENCE_THRESHOLD

    clusters_out: list[FlagCluster] = []
    chunks = list(chunks)
    for chunk in chunks:
        for cat in enabled:
            all_passes: list[DetectionPass] = []
            for variant in ("v1", "v2", "v3"):
                all_passes.extend(_run_pass(chunk, cat, variant))
            if not all_passes:
                continue
            groups = _cluster_passes(all_passes, config.SPAN_IOU_THRESHOLD)
            for group in groups:
                by_pass: dict[str, DetectionPass] = {}
                for p in group:
                    cur = by_pass.get(p.pass_id)
                    if cur is None or p.confidence > cur.confidence:
                        by_pass[p.pass_id] = p
                dedup = list(by_pass.values())
                n = len(dedup)
                agreement = n / 3.0
                mean_conf = sum(p.confidence for p in dedup) / n
                lo = min(p.span_char_start for p in dedup)
                hi = max(p.span_char_end for p in dedup)
                rep = max(dedup, key=lambda x: x.confidence)
                status = "CONFIRMED" if n >= thr else "REVIEW_QUEUE"
                if status == "CONFIRMED" and mean_conf < confs.get(cat, 0.5):
                    status = "REVIEW_QUEUE"
                probe: NegativeProbe | None = None
                if status == "CONFIRMED" and not disable_neg_probe and cat not in config.GRAPH_CATEGORIES:
                    probe = _negative_probe(chunk, cat, rep.span_text)
                    if probe and probe.disagrees:
                        mean_conf = max(0.0, mean_conf - 0.2)
                        if mean_conf < confs.get(cat, 0.5):
                            status = "REVIEW_QUEUE"
                clusters_out.append(
                    FlagCluster(
                        id=f"fc_{uuid.uuid4().hex[:10]}",
                        chunk_id=chunk.id,
                        category=cat,
                        span_text=rep.span_text,
                        span_char_start=lo,
                        span_char_end=hi,
                        mean_confidence=round(mean_conf, 3),
                        agreement_rate=round(agreement, 3),
                        passes=dedup,
                        negative_probe=probe,
                        status=status,
                    )
                )
    return clusters_out


# ---------------------------------------------------------------------------
# Compatibility shim: `detect` routes to dual-scoring by default
# ---------------------------------------------------------------------------


def detect(chunks, **kwargs):
    """Default detector — dual scoring. Returns DualScoredFlag list.

    Set config.USE_LEGACY_ENSEMBLE=True (or pass use_legacy=True) to get FlagCluster list from the ensemble.
    """
    if kwargs.pop("use_legacy", False) or getattr(config, "USE_LEGACY_ENSEMBLE", False):
        return detect_legacy_ensemble(chunks, **kwargs)
    return detect_dual(chunks, **kwargs)
