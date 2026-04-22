"""One-command ingestion orchestrator for the standards corpus and a tender package.

Idempotent: re-runs without --force are near-instant no-ops via a simple file-hash sidecar.

CLI:
  python scripts/ingest_all.py --what standards
  python scripts/ingest_all.py --what tender --tender sample_01_synthetic_cpwd
  python scripts/ingest_all.py --what standards+tender --tender sample_01_synthetic_cpwd
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.chunker import chunk_pages  # noqa: E402
from src.embeddings import VectorStore  # noqa: E402
from src.parser import parse_many  # noqa: E402


def _ingest_sidecar(path: Path) -> Path:
    return ROOT / "standards" / "processed" / (path.stem + ".ingested.json")


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def ingest_standards(force: bool = False) -> dict:
    cat = yaml.safe_load((ROOT / "standards" / "metadata" / "catalog.yaml").read_text(encoding="utf-8"))
    entries = [e for e in (cat.get("entries") or []) if e.get("status") == "OK"]
    raw_dir = ROOT / "standards" / "raw"
    vs = VectorStore()
    summary = {"attempted": 0, "ingested": 0, "skipped": 0, "chunks": 0, "bytes": 0, "wall_s": 0.0}
    t0 = time.time()
    for e in entries:
        summary["attempted"] += 1
        pdf = raw_dir / (e.get("local_path") or "")
        if not pdf.exists():
            continue
        side = _ingest_sidecar(pdf)
        h = _file_hash(pdf)
        if side.exists() and not force:
            try:
                existing = json.loads(side.read_text(encoding="utf-8"))
                if existing.get("hash") == h:
                    summary["skipped"] += 1
                    continue
            except Exception:
                pass
        pages = parse_many([pdf])
        chunks = chunk_pages(pages, max_tokens=config.CHUNK_MAX_TOKENS, overlap_tokens=config.CHUNK_OVERLAP)
        # annotate with source_type and topic
        for c in chunks:
            c.document_type = "Standard"
        # Use the standards collection
        n = vs.add_standards_chunks(chunks, source_type=("CPWD" if e.get("priority") == 2 else "IS"), topic=e.get("topic", ""))
        summary["ingested"] += 1
        summary["chunks"] += n
        summary["bytes"] += pdf.stat().st_size
        side.write_text(json.dumps({"hash": h, "chunks": n, "code": e.get("code")}), encoding="utf-8")
    summary["wall_s"] = round(time.time() - t0, 2)
    return summary


def ingest_tender(short_name: str, force: bool = False) -> dict:
    pkg = ROOT / "tenders" / "real" / short_name
    manifest_path = pkg / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    mf = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    vs = VectorStore()
    vs.reset_package(package_id=short_name)
    chunks_total = 0
    for d in mf.get("documents") or []:
        pdf = pkg / "raw" / d.get("filename", "")
        if not pdf.exists():
            continue
        pages = parse_many([pdf])
        chunks = chunk_pages(pages, max_tokens=config.CHUNK_MAX_TOKENS, overlap_tokens=config.CHUNK_OVERLAP)
        for c in chunks:
            c.package_id = short_name
            c.document_type = d.get("doc_role")
        vs.add_chunks(chunks, collection="package")
        chunks_total += len(chunks)
    return {"tender": short_name, "chunks": chunks_total, "documents": len(mf.get("documents") or [])}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--what", default="standards+tender", help="standards | tender | standards+tender")
    p.add_argument("--tender", default=None, help="tender short-name (under tenders/real/)")
    p.add_argument("--force", action="store_true")
    a = p.parse_args()

    report: dict[str, dict] = {}
    if "standards" in a.what:
        report["standards"] = ingest_standards(force=a.force)
        print("standards:", json.dumps(report["standards"]))
    if "tender" in a.what:
        if not a.tender:
            print("--tender is required when ingesting tender", file=sys.stderr)
            sys.exit(2)
        report["tender"] = ingest_tender(a.tender, force=a.force)
        print("tender:", json.dumps(report["tender"]))

    out = ROOT / "experiments" / "ops_readiness" / "ingest_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
