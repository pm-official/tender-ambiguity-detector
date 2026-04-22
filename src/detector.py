"""Three-pass ensemble detector with negative-control probe (G1 + G2)."""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from . import config
from .schemas import Chunk, DetectionPass, FlagCluster, NegativeProbe
from .utils import active_run_dir, call_llm, iou, logger, render

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class _FlagItem(BaseModel):
    span_text: str
    span_char_start: int = 0
    span_char_end: int = 0
    confidence: float = 0.5
    justification: str = ""


class _DetectionResponse(BaseModel):
    flags: list[_FlagItem] = Field(default_factory=list)


class _ProbeResponse(BaseModel):
    disagrees: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Span normalisation
# ---------------------------------------------------------------------------


def _locate_span(text: str, span_text: str, hint_start: int = 0, hint_end: int = 0) -> tuple[int, int]:
    """If the model's offsets are wrong, find the span in the chunk text."""
    if 0 <= hint_start < hint_end <= len(text) and text[hint_start:hint_end].strip() == span_text.strip():
        return hint_start, hint_end
    idx = text.find(span_text)
    if idx >= 0:
        return idx, idx + len(span_text)
    # fuzzy fallback — find first 20 chars
    probe = span_text[:20].strip()
    if probe:
        idx = text.find(probe)
        if idx >= 0:
            return idx, idx + len(span_text)
    return 0, 0


# ---------------------------------------------------------------------------
# One pass
# ---------------------------------------------------------------------------


def _run_pass(chunk: Chunk, category: str, variant: str) -> list[DetectionPass]:
    suffix = "" if variant == "v1" else f"_{variant}"
    prompt_name = f"detection_{category}{suffix}.txt"
    prompt = render(prompt_name, CHUNK_TEXT=chunk.text)
    try:
        resp, _ = call_llm(
            model=config.DETECTION_MODEL,
            prompt=prompt,
            stage=f"detect_{category}_{variant}",
            response_schema=_DetectionResponse,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("detect pass failed cat=%s variant=%s chunk=%s: %s", category, variant, chunk.id, e)
        return []

    passes: list[DetectionPass] = []
    for item in resp.flags:
        s, e = _locate_span(chunk.text, item.span_text, item.span_char_start, item.span_char_end)
        if e <= s:
            continue
        passes.append(
            DetectionPass(
                pass_id=variant,
                category=category,
                chunk_id=chunk.id,
                span_text=item.span_text,
                span_char_start=s,
                span_char_end=e,
                confidence=max(0.0, min(1.0, item.confidence)),
                justification=item.justification,
            )
        )
    return passes


# ---------------------------------------------------------------------------
# IoU clustering
# ---------------------------------------------------------------------------


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
# Detection entry point
# ---------------------------------------------------------------------------


def detect(
    chunks: Iterable[Chunk],
    *,
    enabled_categories: list[str] | None = None,
    agreement_threshold: int | None = None,
    confidence_thresholds: dict[str, float] | None = None,
    disable_neg_probe: bool = False,
    progress_cb=None,
) -> list[FlagCluster]:
    enabled = enabled_categories or config.ENABLED_CATEGORIES
    thresh = agreement_threshold if agreement_threshold is not None else config.DETECTION_AGREEMENT_THRESHOLD
    confs = confidence_thresholds or config.DETECTION_CONFIDENCE_THRESHOLD

    clusters_out: list[FlagCluster] = []
    passes_log_rows: list[dict] = []

    chunks = list(chunks)
    total_steps = len(chunks) * len(enabled)
    step = 0
    for chunk in chunks:
        for cat in enabled:
            step += 1
            if progress_cb:
                progress_cb(step, total_steps, f"Detect {cat} on {chunk.id}")
            all_passes: list[DetectionPass] = []
            for variant in ("v1", "v2", "v3"):
                passes = _run_pass(chunk, cat, variant)
                all_passes.extend(passes)
                for p in passes:
                    passes_log_rows.append(p.model_dump())
            if not all_passes:
                continue
            groups = _cluster_passes(all_passes, config.SPAN_IOU_THRESHOLD)
            for group in groups:
                # Deduplicate per pass_id by keeping max-confidence within a cluster.
                by_pass: dict[str, DetectionPass] = {}
                for p in group:
                    cur = by_pass.get(p.pass_id)
                    if cur is None or p.confidence > cur.confidence:
                        by_pass[p.pass_id] = p
                dedup = list(by_pass.values())
                n = len(dedup)
                agreement = n / 3.0
                mean_conf = sum(p.confidence for p in dedup) / n
                # pick representative span: the widest window that covers all
                lo = min(p.span_char_start for p in dedup)
                hi = max(p.span_char_end for p in dedup)
                rep = max(dedup, key=lambda x: x.confidence)
                status = "CONFIRMED" if n >= thresh else "REVIEW_QUEUE"
                # per-category confidence gate (only for CONFIRMED)
                if status == "CONFIRMED" and mean_conf < confs.get(cat, 0.5):
                    status = "REVIEW_QUEUE"
                probe: NegativeProbe | None = None
                if status == "CONFIRMED" and not disable_neg_probe and cat not in config.GRAPH_CATEGORIES:
                    probe = _negative_probe(chunk, cat, rep.span_text)
                    if probe and probe.disagrees:
                        mean_conf = max(0.0, mean_conf - 0.2)
                        if mean_conf < confs.get(cat, 0.5):
                            status = "REVIEW_QUEUE"
                cluster = FlagCluster(
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
                clusters_out.append(cluster)

    # Persist transparency log
    try:
        p = active_run_dir() / "detection_passes.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for row in passes_log_rows:
                f.write(json.dumps(row) + "\n")
    except Exception as e:
        logger.warning("failed to write detection_passes: %s", e)

    return clusters_out
