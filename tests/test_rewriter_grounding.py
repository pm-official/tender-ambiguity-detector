from src.rewriter import STANDARDS_REF_RE, _all_refs, _normalise


def test_is_ref_regex_matches_common_forms():
    cases = ["IS 456:2000", "IS-456", "IS 456", "IS:456", "IS 1343-1980"]
    for s in cases:
        assert STANDARDS_REF_RE.search(s)


def test_cpwd_ref_regex_matches():
    cases = ["CPWD Section 3.2", "CPWD 2019 Section 4.1.2", "CPWD Sec 7"]
    for s in cases:
        assert STANDARDS_REF_RE.search(s)


def test_all_refs_extraction():
    texts = ["Per IS 456:2000 and IS-15546.", "See clause in IS 383 and CPWD Section 4.1."]
    refs = _all_refs(texts)
    assert any("456" in r for r in refs)
    assert any("15546" in r for r in refs)
    assert any("383" in r for r in refs)
    assert any("CPWD" in r for r in refs)


def test_normalise_idempotent():
    assert _normalise("IS 456:2000") == _normalise("IS-456:2000")
