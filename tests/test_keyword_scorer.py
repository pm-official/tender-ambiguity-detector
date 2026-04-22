from src.keyword_scorer import load_lexicon, score_chunk
from src.schemas import Chunk


def _chunk(text: str) -> Chunk:
    return Chunk(id="c1", doc_id="d", page=1, text=text)


def test_lexicons_loadable_for_all_categories():
    for cat in "FBIAEGHJ":
        lex = load_lexicon(cat)
        assert isinstance(lex, list)


def test_b_score_triggers_on_adequate_drainage():
    c = _chunk("Contractor shall provide adequate drainage around the foundation.")
    score, matches = score_chunk(c, "B")
    assert score > 0.0
    terms = {m.term for m in matches}
    assert "adequate" in terms


def test_forbid_numeric_context_suppresses_match():
    # 'adequate' is flagged only when not near a numeric/IS reference
    c = _chunk("Adequate drainage shall conform to IS 1742 capacity of 50 l/s.")
    score, matches = score_chunk(c, "B")
    # at least one match should be suppressed by forbid_numeric_nearby
    assert not any(m.term == "adequate" for m in matches)


def test_score_capped_at_one():
    # pack many terms to force a huge raw sum
    big = " ".join(["adequate reasonable sufficient satisfactory"] * 40)
    c = _chunk(big)
    score, _ = score_chunk(c, "B")
    assert 0.0 <= score <= 1.0


def test_j_lexicon_catches_apply_primer():
    c = _chunk("Apply primer coat on the cleaned surface.")
    score, matches = score_chunk(c, "J")
    assert score > 0.0
    assert any("primer" in m.term for m in matches)
