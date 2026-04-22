"""Download a real tender package given a short-name and newline-delimited URLs.

Writes tenders/real/<short-name>/raw/*.pdf, manifest.yaml, download_log.jsonl.
Includes filename-keyword heuristic to auto-classify doc_role.

Fallback: when real portals are unreachable, `scripts/make_synthetic_package.py` emits a labelled
synthetic package without calling this script.

CLI:
  echo 'https://...NIT.pdf\nhttps://...BOQ.pdf' | python scripts/download_tender.py --name sample_02_foo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

try:
    import fitz  # pymupdf
    _HAS_FITZ = True
except Exception:
    _HAS_FITZ = False

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "TAD-research/1.0 (+mailto:sanjukharat90@gmail.com)"


def _auto_role(fname: str) -> str:
    low = fname.lower()
    for kw, role in [
        ("nit", "NIT"),
        ("boq", "BOQ"),
        ("schedule", "BOQ"),
        ("tech_spec", "Technical Specifications"),
        ("particular_spec", "Technical Specifications"),
        ("spec", "Technical Specifications"),
        ("gcc", "GCC"),
        ("general_conditions", "GCC"),
        ("particular_conditions", "Additional Conditions"),
        ("additional", "Additional Conditions"),
        ("conditions", "Conditions of Contract"),
        ("corrigendum", "Addendum"),
        ("addendum", "Addendum"),
        ("drawing", "Drawing"),
        ("dwg", "Drawing"),
    ]:
        if kw in low:
            return role
    return "Other"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True, help="package short-name")
    p.add_argument("--urls-file", help="file with one URL per line; default reads stdin")
    p.add_argument("--title", default="")
    p.add_argument("--value-crore", type=float, default=0.0)
    p.add_argument("--source-portal", default="unknown")
    args = p.parse_args()

    urls: list[str] = []
    if args.urls_file:
        urls = [u.strip() for u in Path(args.urls_file).read_text(encoding="utf-8").splitlines() if u.strip()]
    else:
        urls = [u.strip() for u in sys.stdin.readlines() if u.strip()]
    if not urls:
        print("no URLs provided", file=sys.stderr)
        sys.exit(2)

    pkg = ROOT / "tenders" / "real" / args.name
    raw = pkg / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    log = pkg / "download_log.jsonl"

    session = requests.Session()
    docs_meta = []
    for url in urls:
        fname = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("/")[-1]) or f"file_{len(docs_meta)+1}.pdf"
        dest = raw / fname
        row = {"ts": datetime.now(timezone.utc).isoformat(), "url": url, "filename": fname}
        try:
            with session.get(url, stream=True, timeout=60, headers={"User-Agent": USER_AGENT}) as resp:
                resp.raise_for_status()
                with dest.open("wb") as f:
                    for chunk in resp.iter_content(1 << 16):
                        if chunk:
                            f.write(chunk)
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
            pages = 0
            text_extractable = False
            if _HAS_FITZ:
                try:
                    with fitz.open(str(dest)) as d:
                        pages = len(d)
                        text_extractable = bool((d[0].get_text("text") or "").strip()) if pages else False
                except Exception:
                    pass
            row.update({"ok": True, "sha256": h, "bytes": dest.stat().st_size, "pages": pages, "text_extractable": text_extractable})
            docs_meta.append({
                "filename": fname,
                "doc_role": _auto_role(fname),
                "pages": pages,
                "text_extractable": text_extractable,
                "page_range": None,
                "analyse": True,
            })
        except Exception as exc:
            row.update({"ok": False, "error": str(exc)})
            print(f"FAILED {url}: {exc}", file=sys.stderr)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        time.sleep(2)

    manifest = {
        "package_id": args.name,
        "short_name": args.name,
        "source_portal": args.source_portal,
        "title": args.title or args.name,
        "value_crore": args.value_crore,
        "opened_on": datetime.now(timezone.utc).date().isoformat(),
        "synthetic": False,
        "documents": docs_meta,
    }
    (pkg / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"wrote {pkg/'manifest.yaml'}")


if __name__ == "__main__":
    main()
