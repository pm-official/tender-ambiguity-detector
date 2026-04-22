from src.rewriter import IS_REF_RE, _all_is_refs, _normalize_ref


def test_is_ref_regex_matches_common_forms():
    cases = ["IS 456:2000", "IS-456", "IS 456", "IS:456", "IS 1343-1980"]
    for s in cases:
        assert IS_REF_RE.search(s)


def test_all_is_refs_extraction():
    texts = ["Per IS 456:2000 and IS-15546.", "See clause in IS 383."]
    refs = _all_is_refs(texts)
    assert any("456" in r for r in refs)
    assert any("15546" in r for r in refs)
    assert any("383" in r for r in refs)


def test_normalize_ref_idempotent():
    assert _normalize_ref("IS 456:2000") == _normalize_ref("IS-456:2000")
