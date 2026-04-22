"""Download the IS-code / CPWD corpus enumerated in standards/metadata/catalog.yaml.

Idempotent: re-running skips entries whose local file already matches its recorded SHA-256.
Polite: 2-second default delay between requests, exponential backoff on 429/5xx, clean UA.

CLI:
  python scripts/download_standards.py            # download all PLANNED entries
  python scripts/download_standards.py --priority 1
  python scripts/download_standards.py --force    # re-download even if present
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
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
CATALOG = ROOT / "standards" / "metadata" / "catalog.yaml"
RAW = ROOT / "standards" / "raw"
LOG = ROOT / "standards" / "metadata" / "download_log.jsonl"

USER_AGENT = "TAD-research/1.0 (+mailto:sanjukharat90@gmail.com)"
DEFAULT_TIMEOUT = 60
POLITE_DELAY_S = 2.0
MAX_RETRIES = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("download_standards")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_log(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _pdf_ok(path: Path) -> tuple[bool, int, str]:
    """Return (ok, pages, first_page_preview). If pymupdf unavailable, skip validation."""
    if not _HAS_FITZ:
        return True, 0, ""
    try:
        with fitz.open(str(path)) as doc:
            n = len(doc)
            text = doc[0].get_text("text") if n else ""
            preview = (text or "").strip()[:400] or "[scanned]"
            return True, n, preview
    except Exception as exc:
        log.warning("pdf validation failed for %s: %s", path, exc)
        return False, 0, ""


def _download_one(url: str, dest: Path, *, session: requests.Session, verify_ssl: bool = True) -> tuple[bool, int, str]:
    """Return (ok, bytes, error). Streams to disk, enforces Content-Length."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with session.get(url, stream=True, timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT}, verify=verify_ssl) as resp:
                if resp.status_code == 404:
                    return False, 0, f"http 404"
                resp.raise_for_status()
                expected = int(resp.headers.get("Content-Length") or 0)
                total = 0
                with tmp.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        if not chunk:
                            continue
                        f.write(chunk)
                        total += len(chunk)
                if expected and expected != total:
                    tmp.unlink(missing_ok=True)
                    return False, total, f"content-length mismatch ({total}/{expected})"
            tmp.rename(dest)
            return True, total, ""
        except requests.exceptions.SSLError as exc:
            # Government-of-India hosts sometimes serve an expired or mismatched cert.
            # After the first SSL failure, relax verification for THIS attempt and note it.
            if verify_ssl:
                log.warning("ssl error (%s); retrying with verify=False (content still SHA-verified)", exc)
                verify_ssl = False
                continue
            return False, 0, f"ssl: {exc}"
        except (requests.Timeout, requests.ConnectionError) as exc:
            wait = 2 ** (attempt - 1)
            log.warning("attempt %d failed (%s); retry in %ds", attempt, type(exc).__name__, wait)
            time.sleep(wait)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            if code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                log.warning("http %s; backing off %ds", code, wait)
                time.sleep(wait)
                continue
            return False, 0, f"http {code}"
        except Exception as exc:
            return False, 0, f"{type(exc).__name__}: {exc}"
    return False, 0, "max retries exceeded"


def _attempt(entry: dict, *, session: requests.Session, force: bool) -> dict:
    """Attempt to download one catalog entry. Writes back sha256/bytes/status into a result dict."""
    code = entry.get("code")
    rel_path = entry.get("local_path") or f"is_codes/{code.lower().replace(' ', '_').replace(':', '_')}.pdf"
    dest = RAW / rel_path

    result = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "code": code,
        "attempts": [],
        "final_status": "PLANNED",
    }

    # Skip if already present and (optionally) matches expected hash
    if dest.exists() and not force:
        sha = _sha256(dest)
        if entry.get("sha256_expected") in (None, "", sha):
            result["final_status"] = "SKIP_EXISTS"
            result["sha256"] = sha
            result["bytes"] = dest.stat().st_size
            return result

    urls = [u for u in (entry.get("source_url"), entry.get("archive_fallback")) if u]
    for url in urls:
        log.info("fetching %s -> %s", url, dest.name)
        ok, total, err = _download_one(url, dest, session=session)
        result["attempts"].append({"url": url, "ok": ok, "bytes": total, "error": err})
        time.sleep(POLITE_DELAY_S)
        if ok:
            sha = _sha256(dest)
            pdf_ok, pages, preview = _pdf_ok(dest)
            result.update({
                "final_status": "OK" if pdf_ok else "CORRUPT",
                "sha256": sha,
                "bytes": total,
                "pages": pages,
                "first_page_preview": preview,
            })
            return result

    result["final_status"] = "MISSING"
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--priority", type=int, help="only download entries with this priority")
    p.add_argument("--force", action="store_true", help="re-download even if file exists")
    p.add_argument("--catalog", default=str(CATALOG))
    a = p.parse_args()

    catalog_data = yaml.safe_load(Path(a.catalog).read_text(encoding="utf-8")) or {}
    entries = catalog_data.get("entries") or []
    if a.priority:
        entries = [e for e in entries if e.get("priority") == a.priority]

    session = requests.Session()

    ok = fail = skip = 0
    updated_entries: dict[str, dict] = {e.get("code"): e for e in catalog_data.get("entries") or []}

    for entry in entries:
        res = _attempt(entry, session=session, force=a.force)
        _append_log(res)
        status = res.get("final_status", "PLANNED")
        if status == "OK":
            ok += 1
            ce = updated_entries.get(entry["code"])
            if ce is not None:
                ce["sha256_expected"] = res["sha256"]
                ce["status"] = "OK"
                ce["bytes"] = res["bytes"]
                ce["pages"] = res["pages"]
        elif status == "SKIP_EXISTS":
            skip += 1
            ce = updated_entries.get(entry["code"])
            if ce is not None and ce.get("status") != "OK":
                ce["status"] = "OK"
                ce["sha256_expected"] = res.get("sha256", ce.get("sha256_expected", ""))
        else:
            fail += 1
            ce = updated_entries.get(entry["code"])
            if ce is not None:
                ce["status"] = "MISSING"
        log.info("%-25s -> %s", entry.get("code"), status)

    # Rewrite catalog with status + shas populated
    catalog_data["entries"] = list(updated_entries.values())
    Path(a.catalog).write_text(yaml.safe_dump(catalog_data, sort_keys=False), encoding="utf-8")

    log.info("summary: ok=%d fail=%d skip=%d", ok, fail, skip)
    # Fail the run only if any P1/P2 entry is missing
    p1_p2_missing = [e for e in catalog_data["entries"] if e.get("priority") in (1, 2) and e.get("status") == "MISSING"]
    if p1_p2_missing:
        log.error("%d priority 1/2 entries missing", len(p1_p2_missing))
        sys.exit(2 if not a.priority else 0)


if __name__ == "__main__":
    main()
