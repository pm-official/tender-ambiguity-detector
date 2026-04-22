"""Migrate legacy Prompt-3 run outputs so they render in the Prompt-4 UI without crashing.

Walks output/{run_id}/flags.csv and ensures the columns keyword_score, llm_score, combined_score,
and category_name exist. Leaves other fields untouched.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DISPLAY = {
    "F": "Undefined Terms",
    "B": "Vague Qualifiers",
    "I": "Unnamed References",
    "A": "Word-Level Ambiguity",
    "E": "Unclear Pronouns",
    "G": "Priority Conflicts",
    "H": "Numerical Inconsistencies",
    "J": "Incomplete Specifications",
}


def migrate_dir(output_dir: Path) -> int:
    n = 0
    for run_dir in sorted(p for p in output_dir.iterdir() if p.is_dir()):
        flags_csv = run_dir / "flags.csv"
        if not flags_csv.exists():
            continue
        try:
            df = pd.read_csv(flags_csv)
        except Exception:
            continue
        changed = False
        for col in ("keyword_score", "llm_score", "combined_score"):
            if col not in df.columns:
                df[col] = None
                changed = True
        if "category_name" not in df.columns and "category" in df.columns:
            df["category_name"] = df["category"].map(DISPLAY).fillna(df["category"])
            changed = True
        if changed:
            df.to_csv(flags_csv, index=False)
            n += 1
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", default="output")
    a = p.parse_args()
    n = migrate_dir(Path(a.output_dir))
    print(f"migrated {n} run(s)")


if __name__ == "__main__":
    main()
