"""LLM-as-Judge annotation protocol (Phases 1-6). Claude-executable."""
from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from . import config
from .schemas import Chunk, FlagCluster
from .utils import call_llm, logger, render


class _JudgeResp(BaseModel):
    decision: str = "UNCERTAIN"
    corrected_category: str | None = None
    reason: str = ""


def phase_2_judge_once(flag: FlagCluster, chunk_text: str, surrounding: str = "") -> _JudgeResp:
    prompt = render(
        "llm_judge_annotation.txt",
        CATEGORY=flag.category,
        SPAN_TEXT=flag.span_text,
        CHUNK_TEXT=chunk_text,
        JUSTIFICATION="; ".join(p.justification for p in flag.passes)[:400],
        SURROUNDING_CONTEXT=surrounding[:2000],
    )
    try:
        r, _ = call_llm(
            model=config.JUDGE_MODEL,
            prompt=prompt,
            stage="protocol_judge",
            response_schema=_JudgeResp,
            temperature=0.0,
        )
        return r
    except Exception as e:
        logger.warning("protocol judge failed flag=%s: %s", flag.id, e)
        return _JudgeResp(decision="UNCERTAIN", reason=f"(judge error: {e})")


def majority_vote(verdicts: list[_JudgeResp]) -> _JudgeResp:
    if not verdicts:
        return _JudgeResp(decision="UNCERTAIN", reason="no verdicts")
    c = Counter(v.decision for v in verdicts)
    top, count = c.most_common(1)[0]
    if count <= len(verdicts) // 2:
        return _JudgeResp(decision="UNCERTAIN", reason="no majority across seeds")
    rep = next(v for v in verdicts if v.decision == top)
    return rep


def run_protocol(
    flags: list[FlagCluster],
    chunks: list[Chunk],
    *,
    seeds: int = 3,
    out_dir: Path | None = None,
) -> dict:
    out_dir = out_dir or (config.OUTPUT_DIR / "annotation" / time.strftime("%Y%m%d_%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    chunk_map = {c.id: c for c in chunks}

    buckets = {"true_positive": [], "false_positive": [], "wrong_category": [], "uncertain": [], "disagree_across_seeds": []}
    phase2_rows = []
    for f in flags:
        chk = chunk_map.get(f.chunk_id)
        if chk is None:
            continue
        surrounding = chk.text
        verdicts = []
        for s in range(seeds):
            v = phase_2_judge_once(f, chk.text, surrounding)
            verdicts.append(v)
            phase2_rows.append({"flag_id": f.id, "seed": s, **v.model_dump()})
        vote = majority_vote(verdicts)
        disagree = len({v.decision for v in verdicts}) > 1
        row = {
            "flag_id": f.id,
            "category": f.category,
            "span_text": f.span_text,
            "chunk_id": f.chunk_id,
            "decision": vote.decision,
            "corrected_category": vote.corrected_category,
            "reason": vote.reason,
            "disagreement_across_seeds": disagree,
        }
        key = {
            "TRUE_POSITIVE": "true_positive",
            "FALSE_POSITIVE": "false_positive",
            "WRONG_CATEGORY": "wrong_category",
            "UNCERTAIN": "uncertain",
        }.get(vote.decision, "uncertain")
        buckets[key].append(row)
        if disagree:
            buckets["disagree_across_seeds"].append(row)

    for k, rows in buckets.items():
        (out_dir / f"{k}.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    (out_dir / "phase2_raw.jsonl").write_text("\n".join(json.dumps(r) for r in phase2_rows), encoding="utf-8")

    # Spot-check queue: 20% of TP (stratified), all uncertain, all disagreements
    random.seed(config.RANDOM_SEED)
    tp_by_cat: dict[str, list] = {}
    for r in buckets["true_positive"]:
        tp_by_cat.setdefault(r["category"], []).append(r)
    tp_sample = []
    for cat, rows in tp_by_cat.items():
        k = max(1, int(round(0.2 * len(rows))))
        tp_sample.extend(random.sample(rows, min(k, len(rows))))
    spot_queue = tp_sample + buckets["uncertain"] + buckets["disagree_across_seeds"]
    (out_dir / "spot_check_queue.jsonl").write_text(
        "\n".join(json.dumps(r) for r in spot_queue), encoding="utf-8"
    )

    report = (
        f"# Annotation protocol report\n\n"
        f"- Candidates evaluated: {len(flags)}\n"
        f"- TRUE_POSITIVE: {len(buckets['true_positive'])}\n"
        f"- FALSE_POSITIVE: {len(buckets['false_positive'])}\n"
        f"- WRONG_CATEGORY: {len(buckets['wrong_category'])}\n"
        f"- UNCERTAIN: {len(buckets['uncertain'])}\n"
        f"- Cross-seed disagreements: {len(buckets['disagree_across_seeds'])}\n"
        f"- Spot-check queue size: {len(spot_queue)}\n"
        f"- Seeds per candidate: {seeds}\n"
        f"- LLM calls spent (Phase 2): {len(flags) * seeds}\n\n"
        f"Next steps: review `spot_check_queue.jsonl` in the Annotate tab, then re-run this script to emit gold.\n"
    )
    (out_dir / "protocol_report.md").write_text(report, encoding="utf-8")

    return {
        "out_dir": str(out_dir),
        "buckets": {k: len(v) for k, v in buckets.items()},
        "report_path": str(out_dir / "protocol_report.md"),
    }
