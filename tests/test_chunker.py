from src.chunker import chunk_pages
from src.parser import ParsedPage


def test_chunker_basic_split():
    page = ParsedPage(
        doc_id="d",
        page=1,
        text="4.1 Scope. The contractor shall do X.\n\n4.2 Materials. Use good aggregate.\n\n4.3 Execution. Apply primer.",
    )
    chunks = chunk_pages([page], max_tokens=100, overlap_tokens=10)
    assert len(chunks) >= 1
    assert all(c.doc_id == "d" for c in chunks)


def test_chunker_multi_page():
    pages = [
        ParsedPage(doc_id="d", page=1, text="Clause 1. Alpha beta gamma."),
        ParsedPage(doc_id="d", page=2, text="Clause 2. Delta epsilon zeta."),
    ]
    chunks = chunk_pages(pages)
    assert {c.page for c in chunks} == {1, 2}


def test_chunker_respects_max_tokens():
    text = "1.1 First clause.\n" + ("word " * 200) + "\n2.1 Second clause.\n" + ("word " * 200)
    page = ParsedPage(doc_id="d", page=1, text=text)
    chunks = chunk_pages([page], max_tokens=100, overlap_tokens=5)
    assert len(chunks) >= 2


def test_chunker_no_clause_markers():
    page = ParsedPage(doc_id="d", page=1, text="Plain paragraph.\n\nAnother paragraph.")
    chunks = chunk_pages([page])
    assert len(chunks) >= 1


def test_chunker_preserves_clause_hint():
    page = ParsedPage(doc_id="d", page=1, text="1.1 Scope. Alpha.")
    chunks = chunk_pages([page])
    assert chunks[0].clause_hint is not None
