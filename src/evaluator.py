"""Precision / recall / F1, false-resolution rate, graph-recall, kappa, confusion matrix."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .utils import iou


def _match_flag(pred: dict, gold_list: list[dict], iou_thresh: float = 0.5) -> dict | None:
    best = None
    best_iou = 0.0
    for g in gold_list:
        if g.get("category") != pred.get("category") or g.get("chunk_id") != pred.get("chunk_id"):
            continue
        ii = iou(
            (pred.get("span_char_start", 0), pred.get("span_char_end", 0)),
            (g.get("span_char_start", 0), g.get("span_char_end", 0)),
        )
        if ii >= iou_thresh and ii > best_iou:
            best = g
            best_iou = ii
    return best


def detection_metrics(predictions: list[dict], gold: list[dict], iou_thresh: float = 0.5) -> dict[str, Any]:
    cats = sorted({p["category"] for p in predictions} | {g["category"] for g in gold})
    rows = []
    for cat in cats:
        pred_c = [p for p in predictions if p["category"] == cat]
        gold_c = [g for g in gold if g["category"] == cat]
        matched_gold_ids = set()
        tp = 0
        for p in pred_c:
            m = _match_flag(p, gold_c, iou_thresh)
            if m is not None:
                tp += 1
                matched_gold_ids.add(id(m))
        fp = len(pred_c) - tp
        fn = len(gold_c) - len(matched_gold_ids)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        rows.append({"category": cat, "precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn})
    df = pd.DataFrame(rows)
    overall = {
        "precision_macro": float(df["precision"].mean() if len(df) else 0.0),
        "recall_macro": float(df["recall"].mean() if len(df) else 0.0),
        "f1_macro": float(df["f1"].mean() if len(df) else 0.0),
    }
    return {"per_category": df.to_dict(orient="records"), "overall": overall}


def false_resolution_rate(resolutions: list[dict], audits: list[dict]) -> float:
    """audits: list of {flag_id, was_actually_resolved: bool} for flags stamped RESOLVED."""
    if not audits:
        return 0.0
    wrong = sum(1 for a in audits if a.get("was_actually_resolved") is False)
    return wrong / len(audits)


def graph_retrieval_recall(retrieved_for_GH: list[dict], gold_GH: list[dict]) -> float:
    if not gold_GH:
        return 0.0
    hits = 0
    for g in gold_GH:
        for r in retrieved_for_GH:
            if r.get("flag_id") == g.get("flag_id"):
                hits += 1
                break
    return hits / len(gold_GH)


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    if not labels_a or len(labels_a) != len(labels_b):
        return 0.0
    all_labels = sorted(set(labels_a) | set(labels_b))
    n = len(labels_a)
    po = sum(1 for x, y in zip(labels_a, labels_b) if x == y) / n
    # expected agreement
    pe = 0.0
    for lab in all_labels:
        p_a = labels_a.count(lab) / n
        p_b = labels_b.count(lab) / n
        pe += p_a * p_b
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def landis_koch(kappa: float) -> str:
    if kappa < 0.00:
        return "poor"
    if kappa < 0.21:
        return "slight"
    if kappa < 0.41:
        return "fair"
    if kappa < 0.61:
        return "moderate"
    if kappa < 0.81:
        return "substantial"
    return "almost perfect"


def report_markdown(metrics: dict[str, Any]) -> str:
    lines = ["## Detection metrics", ""]
    pc = metrics.get("per_category", [])
    if pc:
        lines.append("| Category | Precision | Recall | F1 | TP | FP | FN |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in pc:
            lines.append(
                f"| {r['category']} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} "
                f"| {r['tp']} | {r['fp']} | {r['fn']} |"
            )
    overall = metrics.get("overall", {})
    if overall:
        lines.append(
            f"\nMacro: P={overall['precision_macro']:.3f}  R={overall['recall_macro']:.3f}  F1={overall['f1_macro']:.3f}"
        )
    return "\n".join(lines)
