"""Inter-annotator agreement (Cohen's kappa)."""
from __future__ import annotations

from .evaluator import cohen_kappa, landis_koch


def kappa_report(labels_a: list[str], labels_b: list[str]) -> dict:
    k = cohen_kappa(labels_a, labels_b)
    return {"kappa": k, "interpretation": landis_koch(k), "n": len(labels_a)}
