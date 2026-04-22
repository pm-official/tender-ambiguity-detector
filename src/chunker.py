"""Clause-aware chunking: splits tender text along clause markers, then packs into ~500-token chunks."""
from __future__ import annotations

import re
import uuid
from typing import Iterable

from .parser import ParsedPage
from .schemas import Chunk

# Heuristic clause markers for Indian construction tenders.
CLAUSE_REGEX = re.compile(
    r"^\s*(?:"
    r"(?:Clause|CLAUSE|Article|Section|SECTION|Annexure|Appendix|Schedule)\s+\S+"
    r"|(?:\d+\.\d+(?:\.\d+)*)"
    r"|(?:\([a-z]\))"
    r"|(?:[IVX]+\.)"
    r")\s+",
    re.MULTILINE,
)


def _rough_token_count(text: str) -> int:
    return max(1, len(text.split()))


def _split_on_clauses(text: str) -> list[tuple[int, str]]:
    """Return list of (offset_in_text, segment_text)."""
    matches = list(CLAUSE_REGEX.finditer(text))
    if not matches:
        # fall back to paragraph split
        out: list[tuple[int, str]] = []
        cursor = 0
        for para in re.split(r"\n\s*\n", text):
            out.append((cursor, para))
            cursor += len(para) + 2
        return out
    spans: list[tuple[int, int]] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((start, end))
    return [(s, text[s:e]) for s, e in spans]


def chunk_page(
    page: ParsedPage,
    *,
    max_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    segments = _split_on_clauses(page.text)
    chunks: list[Chunk] = []
    buf_text = ""
    buf_start = 0
    buf_tokens = 0
    buf_clause_hint: str | None = None

    def emit(start_offset: int, text: str, hint: str | None):
        if not text.strip():
            return
        cid = f"{page.doc_id}_p{page.page}_{uuid.uuid4().hex[:6]}"
        chunks.append(
            Chunk(
                id=cid,
                doc_id=page.doc_id,
                page=page.page,
                text=text.strip(),
                clause_hint=hint,
                char_start=start_offset,
                char_end=start_offset + len(text),
            )
        )

    for offset, seg in segments:
        seg_tokens = _rough_token_count(seg)
        first_line = seg.strip().splitlines()[0][:80] if seg.strip() else None

        if buf_tokens + seg_tokens > max_tokens and buf_text:
            emit(buf_start, buf_text, buf_clause_hint)
            # start a new buffer with overlap
            overlap_text = " ".join(buf_text.split()[-overlap_tokens:]) if overlap_tokens else ""
            buf_text = overlap_text + ("\n" if overlap_text else "") + seg
            buf_start = offset - len(overlap_text) if overlap_text else offset
            buf_tokens = _rough_token_count(buf_text)
            buf_clause_hint = first_line
        else:
            if not buf_text:
                buf_start = offset
                buf_clause_hint = first_line
            buf_text = (buf_text + "\n" + seg) if buf_text else seg
            buf_tokens += seg_tokens

    if buf_text:
        emit(buf_start, buf_text, buf_clause_hint)

    return chunks


def chunk_pages(pages: Iterable[ParsedPage], *, max_tokens: int = 500, overlap_tokens: int = 50) -> list[Chunk]:
    out: list[Chunk] = []
    for p in pages:
        out.extend(chunk_page(p, max_tokens=max_tokens, overlap_tokens=overlap_tokens))
    return out
