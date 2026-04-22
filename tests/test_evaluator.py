from src.evaluator import cohen_kappa, detection_metrics, landis_koch


def test_cohen_kappa_trivial():
    a = ["TP", "TP", "FP", "FP", "TP"]
    b = ["TP", "TP", "FP", "FP", "TP"]
    assert cohen_kappa(a, b) == 1.0


def test_cohen_kappa_disagree():
    a = ["TP", "TP", "TP", "TP"]
    b = ["FP", "FP", "FP", "FP"]
    # perfect disagreement with all-labels-same on one side → undefined in naive sense; our impl returns 0
    k = cohen_kappa(a, b)
    assert k <= 0.1


def test_landis_koch_bands():
    assert landis_koch(0.5) == "moderate"
    assert landis_koch(0.85) == "almost perfect"


def test_detection_metrics_basic():
    gold = [{"category": "F", "chunk_id": "c1", "span_char_start": 0, "span_char_end": 10}]
    pred = [{"category": "F", "chunk_id": "c1", "span_char_start": 1, "span_char_end": 11}]
    m = detection_metrics(pred, gold)
    assert m["overall"]["f1_macro"] > 0.0
