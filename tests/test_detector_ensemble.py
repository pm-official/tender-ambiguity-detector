from src.detector import _cluster_passes
from src.schemas import DetectionPass


def _p(pid, s, e, conf=0.8):
    return DetectionPass(
        pass_id=pid, category="F", chunk_id="c1",
        span_text="x", span_char_start=s, span_char_end=e, confidence=conf, justification="",
    )


def test_iou_clustering_merges_overlapping_spans():
    ps = [_p("v1", 0, 10), _p("v2", 2, 12), _p("v3", 100, 110)]
    groups = _cluster_passes(ps, 0.5)
    # v1 and v2 overlap heavily; v3 is separate
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_iou_clustering_separates_non_overlapping():
    ps = [_p("v1", 0, 5), _p("v2", 50, 55)]
    groups = _cluster_passes(ps, 0.5)
    assert len(groups) == 2
