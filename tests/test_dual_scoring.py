from unittest.mock import patch

from src import config
from src.detector import detect_dual
from src.schemas import Chunk


def _chunk(text: str, cid="c1") -> Chunk:
    return Chunk(id=cid, doc_id="d", page=1, text=text, package_id="pkg1")


class _FakeLLM:
    def __init__(self, score=0.8, span="adequate", justification="vague"):
        self.score = score
        self.span = span
        self.justification = justification


def test_combined_formula_at_various_alphas():
    chunk = _chunk("Contractor shall provide adequate drainage around the foundation.")

    # Fake LLM returning a fixed score
    from src.detector import _ScoreResp  # type: ignore
    fake = _ScoreResp(score=0.60, span_text="adequate drainage", span_start=32, justification="vague")

    with patch("src.detector._llm_score", return_value=fake):
        flags_low_alpha = detect_dual(
            [chunk], enabled_categories=["B"], alpha=0.0, threshold=0.3, disable_neg_probe=True
        )
        flags_high_alpha = detect_dual(
            [chunk], enabled_categories=["B"], alpha=1.0, threshold=0.0, disable_neg_probe=True
        )

    assert len(flags_low_alpha) == 1
    # α=0 means combined ≈ llm = 0.60
    assert abs(flags_low_alpha[0].combined_score - 0.60) < 1e-3
    # α=1 means combined ≈ keyword (nonzero because 'adequate' matched)
    assert flags_high_alpha[0].combined_score > 0.0


def test_flag_suppressed_when_below_threshold():
    chunk = _chunk("The works shall be completed on schedule.")  # no lexicon hits

    from src.detector import _ScoreResp  # type: ignore
    fake = _ScoreResp(score=0.1, span_text="", span_start=0, justification="no ambiguity")

    with patch("src.detector._llm_score", return_value=fake):
        flags = detect_dual(
            [chunk], enabled_categories=["B"], alpha=0.3, threshold=0.5, disable_neg_probe=True
        )
    assert flags == []


def test_flag_carries_both_scores_and_matches():
    chunk = _chunk("Contractor shall provide adequate drainage around the foundation.")
    from src.detector import _ScoreResp  # type: ignore
    fake = _ScoreResp(score=0.75, span_text="adequate drainage", span_start=28, justification="vague")
    with patch("src.detector._llm_score", return_value=fake):
        flags = detect_dual(
            [chunk],
            enabled_categories=["B"],
            alpha=0.3,
            threshold=0.3,
            disable_neg_probe=True,
            package_id="pkg1",
        )
    assert flags
    f = flags[0]
    assert f.keyword_score > 0.0
    assert f.llm_score > 0.0
    assert 0.0 <= f.combined_score <= 1.0
    assert f.package_id == "pkg1"
