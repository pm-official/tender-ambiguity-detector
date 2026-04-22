"""Ingest IS-code / CPWD spec PDFs into the standards_chunks collection.

CLI: `python -m src.is_code_ingest --pdf path.pdf --source IS --topic concrete`

No standards text is written into source or fixtures. The user supplies the PDFs; this module
embeds them into the standards collection for Stage-3 retrieval.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .chunker import chunk_pages
from .embeddings import VectorStore
from .parser import parse_many


def ingest_file(
    pdf: Path,
    *,
    source_type: str = "IS",
    topic: str | None = None,
    vs: VectorStore | None = None,
) -> int:
    pages = parse_many([pdf])
    chunks = chunk_pages(pages)
    store = vs or VectorStore()
    return store.add_standards_chunks(chunks, source_type=source_type, topic=topic)


def ingest_dir(is_code_dir: Path, *, source_type: str = "IS", topic: str | None = None) -> int:
    pdfs = list(Path(is_code_dir).glob("*.pdf"))
    if not pdfs:
        return 0
    pages = parse_many(pdfs)
    chunks = chunk_pages(pages)
    vs = VectorStore()
    return vs.add_standards_chunks(chunks, source_type=source_type, topic=topic)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", required=True)
    p.add_argument("--source", choices=["IS", "CPWD"], default="IS")
    p.add_argument("--topic", default=None)
    a = p.parse_args()
    n = ingest_file(Path(a.pdf), source_type=a.source, topic=a.topic)
    print(f"ingested {n} chunks from {a.pdf} (source={a.source}, topic={a.topic})")


if __name__ == "__main__":
    main()
