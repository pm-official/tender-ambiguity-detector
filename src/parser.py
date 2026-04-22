"""PDF -> (page, text) parsing with fallback for scanned or corrupt PDFs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .utils import active_run_dir, logger


@dataclass
class ParsedPage:
    doc_id: str
    page: int
    text: str


def _safe_stem(path: Path) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in path.stem)[:60]


def parse_pdf(path: Path) -> list[ParsedPage]:
    """Parse PDF using pymupdf; returns one ParsedPage per page."""
    import fitz  # pymupdf

    doc_id = _safe_stem(path)
    pages: list[ParsedPage] = []
    try:
        with fitz.open(str(path)) as doc:
            for i, page in enumerate(doc):
                text = page.get_text("text") or ""
                pages.append(ParsedPage(doc_id=doc_id, page=i + 1, text=text))
    except Exception as e:
        logger.error("failed to parse %s: %s", path, e)
        raise
    return pages


def parse_many(paths: Iterable[Path]) -> list[ParsedPage]:
    out: list[ParsedPage] = []
    for p in paths:
        out.extend(parse_pdf(p))
    return out


def write_parse_report(pages: list[ParsedPage], *, out_dir: Path | None = None) -> Path:
    rd = out_dir or active_run_dir()
    report = {
        "n_pages": len(pages),
        "docs": sorted({p.doc_id for p in pages}),
        "total_chars": sum(len(p.text) for p in pages),
        "pages_per_doc": _counts({p.doc_id: 1 for p in pages}, grouper=[p.doc_id for p in pages]),
    }
    path = rd / "parse_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def _counts(_unused: dict, *, grouper: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for g in grouper:
        out[g] = out.get(g, 0) + 1
    return out
