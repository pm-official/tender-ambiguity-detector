from src.schemas import Chunk, DetectionPass, FlagCluster, PipelineResult, Resolution, Rewrite


def test_schemas_roundtrip():
    c = Chunk(id="c1", doc_id="d1", page=1, text="Some text")
    assert Chunk.model_validate(c.model_dump()) == c

    dp = DetectionPass(
        pass_id="v1", category="F", chunk_id="c1",
        span_text="suitable", span_char_start=0, span_char_end=8,
        confidence=0.7, justification="x",
    )
    fc = FlagCluster(
        id="fc1", chunk_id="c1", category="F", span_text="suitable",
        span_char_start=0, span_char_end=8, mean_confidence=0.7, agreement_rate=0.67,
        passes=[dp],
    )
    assert FlagCluster.model_validate(fc.model_dump()).id == "fc1"

    r = Resolution(flag_id="fc1", verdict="UNRESOLVED", reasoning="n/a")
    rw = Rewrite(flag_id="fc1", status="INSUFFICIENT_GROUNDING")
    pr = PipelineResult(
        run_id="r", doc_ids=["d1"], n_chunks=1, n_flags_confirmed=1, n_flags_review=0,
        n_resolutions=1, n_rewrites=0, elapsed_seconds=1.0,
    )
    for m in [r, rw, pr]:
        assert m.model_dump_json()
