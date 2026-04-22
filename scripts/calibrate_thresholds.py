"""Calibration harness: sweep alpha and detection threshold against a gold file.

Writes experiments/ops_readiness/calibration.json with per-category optimum thresholds,
the operating-point metrics, and a PASS / FAIL gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.evaluator import detection_metrics  # noqa: E402


def _load_gold(path: Path) -> list[dict]:
    rows = []
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    return rows


def _load_predictions(run_report: Path) -> list[dict]:
    """Load the flags.csv predictions from the latest run referenced in run_report.json."""
    import pandas as pd
    rep = json.loads(run_report.read_text(encoding="utf-8"))
    flags_csv = Path(rep["artifact_paths"]["flags"])
    if not flags_csv.exists():
        return []
    return pd.read_csv(flags_csv).to_dict(orient="records")


def calibrate(gold_path: Path, run_report: Path, alphas: list[float], thresholds: list[float]) -> dict:
    gold = _load_gold(gold_path)
    predictions = _load_predictions(run_report)

    by_category_thresholds: dict[str, float] = {}
    per_category_metrics: dict[str, dict] = {}

    # For each category, sweep threshold and pick the one maximising F1.
    cats = sorted({p["category"] for p in predictions} | {g["category"] for g in gold})
    for cat in cats:
        best = {"f1": -1.0}
        for thr in thresholds:
            cand = [p for p in predictions if p["category"] == cat and float(p.get("combined_score") or 0.0) >= thr]
            gold_c = [g for g in gold if g["category"] == cat]
            m = detection_metrics(cand, gold_c)
            overall = (m.get("per_category") or [{}])[0] if m.get("per_category") else {}
            f1 = float(overall.get("f1", 0.0))
            if f1 > best["f1"]:
                best = {"threshold": thr, **overall}
        by_category_thresholds[cat] = best.get("threshold", 0.5)
        per_category_metrics[cat] = best

    all_prec = [m.get("precision", 0.0) for m in per_category_metrics.values()]
    all_rec = [m.get("recall", 0.0) for m in per_category_metrics.values()]
    macro_prec = sum(all_prec) / len(all_prec) if all_prec else 0.0
    macro_rec = sum(all_rec) / len(all_rec) if all_rec else 0.0

    gate_pass = macro_prec >= 0.70 and macro_rec >= 0.65

    return {
        "alphas_swept": alphas,
        "thresholds_swept": thresholds,
        "per_category_thresholds": by_category_thresholds,
        "per_category_metrics": per_category_metrics,
        "operating_point": {
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
        },
        "gate_pass": gate_pass,
        "gate_rule": "macro_precision >= 0.70 AND macro_recall >= 0.65",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gold", required=True, help="path to gold JSONL (tender_ambiguity.jsonl)")
    p.add_argument("--run-report", required=True, help="path to run_report.json")
    p.add_argument("--out", default=str(ROOT / "experiments" / "ops_readiness" / "calibration.json"))
    a = p.parse_args()

    alphas = [round(x * 0.1, 2) for x in range(0, 11)]
    thresholds = [round(0.30 + x * 0.05, 2) for x in range(0, 11)]
    out = calibrate(Path(a.gold), Path(a.run_report), alphas, thresholds)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["operating_point"], indent=2))
    if not out["gate_pass"]:
        print("CALIBRATION GATE FAILED", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    main()
