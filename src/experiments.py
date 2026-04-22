"""Ablation runner. CLI: python -m src.experiments --run-all."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .pipeline import run_pipeline


ABLATIONS = {
    "baseline": dict(),
    "ensemble_off": dict(single_pass=True),  # informational; enforced via config tweaks in detector
    "no_neg_probe": dict(disable_neg_probe=True),
    "no_citation_judge": dict(disable_citation_judge=True),
    "no_ground_verify": dict(disable_ground_verify=True),
}


def main(pdfs: list[Path]):
    out = Path(config.OUTPUT_DIR) / "experiments"
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name, kwargs in ABLATIONS.items():
        print(f"[experiments] running {name}")
        res = run_pipeline(pdfs, run_id=f"ablation_{name}", **kwargs)
        summary[name] = {
            "run_id": res.run_id,
            "n_flags_confirmed": res.n_flags_confirmed,
            "n_resolutions": res.n_resolutions,
            "n_rewrites": res.n_rewrites,
            "elapsed_s": res.elapsed_seconds,
            "per_cat": res.per_category_counts,
        }
    (out / "summary.md").write_text(_md(summary), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[experiments] done → {out/'summary.md'}")


def _md(summary: dict) -> str:
    lines = ["# Ablations — summary\n", "| Ablation | Flags | Resolutions | Rewrites | Elapsed (s) |", "|---|---|---|---|---|"]
    for name, s in summary.items():
        lines.append(
            f"| {name} | {s['n_flags_confirmed']} | {s['n_resolutions']} | {s['n_rewrites']} | {s['elapsed_s']:.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pdfs", nargs="+", required=True)
    p.add_argument("--run-all", action="store_true")
    a = p.parse_args()
    if a.run_all:
        main([Path(x) for x in a.pdfs])
