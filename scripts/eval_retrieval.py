"""Evaluate standards-corpus retrieval on gold/standards_qa.jsonl.

Reports hit@1, hit@3, mrr. Gate: hit@3 >= 0.70 per spec §5.2.

A retrieval is a "hit" if the `expected_source` code string (e.g. "IS 456:2000")
appears in the retrieved chunk's `meta.source_type + ...` OR the retrieved chunk's
text contains the code. We use a lenient string-in-text match because chunk metadata
does not always carry the canonical code.

CLI:
  python scripts/eval_retrieval.py [--top-k 3] [--gate 0.70]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.embeddings import VectorStore  # noqa: E402


def _matches(expected_source: str, chunk) -> bool:
    """Flexible match: substring of expected_source present in chunk text or meta."""
    blob = (chunk.text or "") + " " + " ".join(str(v) for v in (chunk.meta or {}).values())
    # Normalise: strip punctuation and whitespace for a robust compare
    expected_norm = re.sub(r"\W+", "", expected_source).lower()
    blob_norm = re.sub(r"\W+", "", blob).lower()
    # e.g. "IS 456:2000" -> "is4562000"; require the number part to appear.
    number_part = re.sub(r"[^0-9]", "", expected_source.split(":")[0])
    if number_part and number_part in blob_norm:
        return True
    return expected_norm in blob_norm


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gold", default=str(ROOT / "gold" / "standards_qa.jsonl"))
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--gate", type=float, default=0.70)
    p.add_argument("--out", default=str(ROOT / "experiments" / "ops_readiness" / "retrieval_eval.json"))
    a = p.parse_args()

    gold = [json.loads(ln) for ln in Path(a.gold).read_text(encoding="utf-8").splitlines() if ln.strip()]
    vs = VectorStore()
    stats = {"n": len(gold), "hit@1": 0, "hit@3": 0, "mrr_sum": 0.0, "per_item": []}

    if vs.standards.count() == 0:
        print("standards collection is EMPTY — run scripts/ingest_all.py --what standards first", file=sys.stderr)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"error": "standards_empty"}), encoding="utf-8")
        sys.exit(3)

    for row in gold:
        retrieved = vs.query_standards(row["question"], top_k=a.top_k)
        rank = None
        for i, c in enumerate(retrieved, start=1):
            if _matches(row["expected_source"], c):
                rank = i
                break
        item = {"id": row["id"], "rank": rank, "n_retrieved": len(retrieved)}
        stats["per_item"].append(item)
        if rank == 1:
            stats["hit@1"] += 1
        if rank is not None and rank <= a.top_k:
            stats["hit@3"] += 1
        if rank:
            stats["mrr_sum"] += 1.0 / rank

    n = stats["n"]
    stats["hit@1_rate"] = round(stats["hit@1"] / n, 4) if n else 0.0
    stats["hit@3_rate"] = round(stats["hit@3"] / n, 4) if n else 0.0
    stats["mrr"] = round(stats["mrr_sum"] / n, 4) if n else 0.0

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"hit@1={stats['hit@1_rate']:.3f}  hit@3={stats['hit@3_rate']:.3f}  mrr={stats['mrr']:.3f}  (n={n})")
    if stats["hit@3_rate"] < a.gate:
        print(f"GATE FAILED: hit@3 {stats['hit@3_rate']:.3f} < {a.gate:.2f}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
