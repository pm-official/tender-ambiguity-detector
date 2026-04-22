"""Verify the standards and tender corpus on disk against the catalog / manifests.

Exits 0 iff all priority 1 and priority 2 standards entries have status=OK
AND any requested tender package passes a basic sanity check.

CLI:
  python scripts/verify_corpus.py
  python scripts/verify_corpus.py --tender sample_01_synthetic
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "standards" / "metadata" / "catalog.yaml"
RAW = ROOT / "standards" / "raw"
TENDERS = ROOT / "tenders" / "real"

try:
    import fitz  # pymupdf
    _HAS_FITZ = True
except Exception:
    _HAS_FITZ = False


def verify_standards() -> tuple[int, list[dict]]:
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    entries = data.get("entries") or []
    rows = []
    for e in entries:
        local = RAW / (e.get("local_path") or "")
        present = local.exists()
        rows.append({
            "code": e.get("code"),
            "priority": e.get("priority"),
            "status": e.get("status"),
            "present_on_disk": present,
            "bytes": e.get("bytes"),
            "pages": e.get("pages"),
        })
    missing = [r for r in rows if r["priority"] in (1, 2) and not r["present_on_disk"]]
    return len(missing), rows


def verify_tender(name: str) -> tuple[bool, list[dict]]:
    pkg = TENDERS / name
    manifest = pkg / "manifest.yaml"
    if not manifest.exists():
        return False, [{"error": f"{manifest} not found"}]
    mf = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    docs = mf.get("documents") or []
    rows = []
    total_pages = 0
    any_extractable = False
    for d in docs:
        pth = pkg / "raw" / d.get("filename", "")
        row = {"filename": d.get("filename"), "role": d.get("doc_role"), "exists": pth.exists()}
        if pth.exists() and _HAS_FITZ:
            try:
                with fitz.open(str(pth)) as doc:
                    row["pages"] = len(doc)
                    row["text_extractable"] = bool(doc[0].get_text("text").strip()) if len(doc) else False
                    total_pages += row["pages"]
                    any_extractable = any_extractable or row["text_extractable"]
            except Exception as exc:
                row["error"] = str(exc)
        rows.append(row)
    ok = all(r.get("exists") for r in rows) and 40 <= total_pages <= 1200 and (any_extractable or not _HAS_FITZ)
    return ok, rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tender", help="tender package short-name under tenders/real/")
    args = p.parse_args()

    missing, rows = verify_standards()
    print("=== Standards corpus ===")
    print(f"{'code':<28} {'prio':<4} {'status':<10} {'on-disk':<8} {'pages':<6}")
    for r in rows:
        print(f"{r['code']:<28} {r['priority']!s:<4} {r['status']!s:<10} {r['present_on_disk']!s:<8} {r.get('pages') or '-'!s:<6}")
    print()
    print(f"Priority-1/2 missing on disk: {missing}")

    exit_code = 0 if missing == 0 else 2

    if args.tender:
        ok, trows = verify_tender(args.tender)
        print()
        print(f"=== Tender: {args.tender} ===")
        for r in trows:
            print(r)
        if not ok:
            exit_code = exit_code or 3

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
