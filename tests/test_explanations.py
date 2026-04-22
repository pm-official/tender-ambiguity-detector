from src import config, explain


def test_categories_all_have_explanations():
    for c in config.ENABLED_CATEGORIES:
        e = explain.explain_or_stub(f"categories.{c}")
        assert e["what"], f"category {c} missing 'what'"


def test_verdicts_all_have_explanations():
    for v in ["RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED"]:
        e = explain.explain_or_stub(f"verdicts.{v}")
        assert e["what"]


def test_stages_have_explanations():
    for s in ["parse", "chunk", "embed", "graph", "resolve", "rewrite", "merge_probe", "judge_citations", "verify_grounding"]:
        e = explain.explain_or_stub(f"stages.{s}")
        assert e["what"]


def test_metrics_have_explanations():
    for m in ["precision", "recall", "f1", "false_resolution_rate", "kappa", "graph_retrieval_recall", "agreement_rate", "mean_confidence"]:
        e = explain.explain_or_stub(f"metrics.{m}")
        assert e["what"]


def test_params_have_explanations():
    for k in config.dump().keys():
        if k in ("DETECTION_CONFIDENCE_THRESHOLD",):
            key = k
        else:
            key = k
        e = explain.explain_or_stub(f"params.{key}")
        assert e["what"], f"param {key} missing explanation"
