"""Run the full TAD pipeline headlessly on a real tender package.

Outputs a full run report to experiments/ops_readiness/run_<ts>/ with timing, counts,
top-10 samples, and a cost estimate.

CLI:
  python scripts/run_end_to_end_demo.py --tender sample_01_synthetic_cpwd
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.pipeline import run_pipeline  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tender", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--cheap-mode", action="store_true", help="force Flash for adjudication (lower cost)")
    a = p.parse_args()

    pkg_dir = ROOT / "tenders" / "real" / a.tender
    mf = yaml.safe_load((pkg_dir / "manifest.yaml").read_text(encoding="utf-8"))
    pdf_paths = [pkg_dir / "raw" / d["filename"] for d in mf.get("documents") or []]
    for p_ in pdf_paths:
        if not p_.exists():
            raise FileNotFoundError(p_)

    if a.cheap_mode:
        os.environ["TAD_CHEAP_MODE"] = "1"
        config.ADJUDICATION_MODEL = config.DETECTION_MODEL  # Flash for adjudication

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = Path(a.out or (ROOT / "experiments" / "ops_readiness" / f"run_{ts}"))
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    progress = []

    def _cb(stage, pct, msg):
        progress.append({"t": round(time.time() - t0, 2), "stage": stage, "pct": pct, "msg": msg})

    types = {d["filename"]: d.get("doc_role", "Other") for d in mf.get("documents") or []}
    analyse_flags = {d["filename"]: bool(d.get("analyse", True)) for d in mf.get("documents") or []}

    result = run_pipeline(
        pdf_paths,
        package_types=types,
        analyse_flags=analyse_flags,
        progress_cb=_cb,
    )
    elapsed = round(time.time() - t0, 2)

    # Cost estimate — rough back-of-envelope
    from pathlib import Path as _P  # noqa
    run_dir = _P(config.OUTPUT_DIR) / result.run_id
    llm_log = run_dir / "llm_calls.jsonl"
    calls_by_stage = {}
    if llm_log.exists():
        for ln in llm_log.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                calls_by_stage[r.get("stage", "?")] = calls_by_stage.get(r.get("stage", "?"), 0) + 1
            except Exception:
                pass
    cost_estimate_usd = 0.0
    # Gemini 2.5 Flash ~ $0.3/1M input tok; Pro ~ $2.5/1M input tok. Assume 2000 tok per call.
    for stage, n in calls_by_stage.items():
        if stage.startswith(("detect_score_", "extract_", "probe_")):
            cost_estimate_usd += n * 2000 / 1_000_000 * 0.30
        elif stage.startswith(("resolve", "judge_", "rewrite")):
            cost_estimate_usd += n * 2000 / 1_000_000 * 2.50

    report = {
        "run_id": result.run_id,
        "tender": a.tender,
        "elapsed_s": elapsed,
        "n_chunks": result.n_chunks,
        "n_flags_confirmed": result.n_flags_confirmed,
        "n_flags_review": result.n_flags_review,
        "n_resolutions": result.n_resolutions,
        "n_rewrites": result.n_rewrites,
        "per_category_counts": result.per_category_counts,
        "llm_calls_by_stage": calls_by_stage,
        "cost_estimate_usd": round(cost_estimate_usd, 4),
        "progress": progress,
        "artifact_paths": result.artifact_paths,
    }
    (out / "run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "cost_report.json").write_text(json.dumps({"usd": round(cost_estimate_usd, 4), "by_stage": calls_by_stage}, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": result.run_id, "elapsed_s": elapsed, "cost_usd": round(cost_estimate_usd, 4)}, indent=2))


if __name__ == "__main__":
    main()
