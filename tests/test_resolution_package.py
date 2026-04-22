from unittest.mock import patch

from src.resolver import _VERDICT_MAP, resolve
from src.schemas import DualScoredFlag, RetrievedContext


def _flag() -> DualScoredFlag:
    return DualScoredFlag(
        id="ds_1",
        chunk_id="c1",
        category="F",
        span_text="suitable aggregate",
        span_char_start=0,
        span_char_end=18,
        keyword_score=0.7,
        llm_score=0.6,
        combined_score=0.63,
        justification="undefined term",
        package_id="pkg1",
    )


def test_verdict_map_accepts_legacy_labels():
    assert _VERDICT_MAP["RESOLVED"] == "RESOLVED_BY_CONTEXT"
    assert _VERDICT_MAP["UNRESOLVED"] == "CONFIRMED_AMBIGUOUS"
    assert _VERDICT_MAP["CONFIRMED_AMBIGUOUS"] == "CONFIRMED_AMBIGUOUS"


class _FakeAdj:
    def __init__(self, verdict="CONFIRMED_AMBIGUOUS", reasoning="n/a", cited=None):
        self.verdict = verdict
        self.reasoning = reasoning
        self.cited_context_ids = cited or []


def test_resolve_emits_new_verdicts():
    flag = _flag()
    ctx = [RetrievedContext(context_id="tender:c2", source="tender", text="Aggregate shall conform to IS 383.", score=0.8)]

    with patch(
        "src.resolver.call_llm",
        return_value=(_FakeAdj(verdict="RESOLVED_BY_CONTEXT", reasoning="covered", cited=["tender:c2"]), None),
    ):
        class _FakeVS:
            def query_package(self, *a, **k):
                return ctx

            def query_tender(self, *a, **k):
                return ctx

        res = resolve(flag, "use suitable aggregate", vector_store=_FakeVS(), disable_citation_judge=True)
        assert res.verdict == "RESOLVED_BY_CONTEXT"
        assert res.stage == "package_context"


def test_resolve_maps_legacy_unresolved_to_confirmed():
    flag = _flag()
    with patch("src.resolver.call_llm", return_value=(_FakeAdj(verdict="UNRESOLVED"), None)):
        class _FakeVS:
            def query_package(self, *a, **k):
                return []

            def query_tender(self, *a, **k):
                return []

        res = resolve(flag, "use suitable aggregate", vector_store=_FakeVS(), disable_citation_judge=True)
        assert res.verdict == "CONFIRMED_AMBIGUOUS"
