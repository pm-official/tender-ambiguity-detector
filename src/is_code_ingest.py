"""Ingest IS-code PDFs (user-supplied) into the is_code_chunks collection.

NOTE: No IS-code text is ever written into source or fixtures. The user adds IS-code PDFs to is_codes/
at runtime; this module embeds them into ChromaDB but never emits their text outside the store.
"""
from __future__ import annotations

from pathlib import Path

from .chunker import chunk_pages
from .embeddings import VectorStore
from .parser import parse_many


def ingest_dir(is_code_dir: Path) -> int:
    pdfs = list(Path(is_code_dir).glob("*.pdf"))
    if not pdfs:
        return 0
    pages = parse_many(pdfs)
    chunks = chunk_pages(pages)
    vs = VectorStore()
    return vs.add_chunks(chunks, collection="is_code")
