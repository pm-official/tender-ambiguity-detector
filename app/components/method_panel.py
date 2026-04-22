"""The 'About this method' standalone tab content."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src import config, explain

from .info_icon import info_popover

ROOT = Path(__file__).resolve().parent.parent.parent


def render_method_panel():
    st.markdown("## About this method")
    st.caption(
        "This page is the one-stop introduction to TAD. "
        "Every number and verdict in the app has an (ℹ) icon that opens a popover like the ones below."
    )

    st.markdown("### The problem")
    st.write(
        "Construction tenders routinely contain ambiguous clauses. Ambiguity drives disputes, cost overruns, "
        "re-tenders and litigation. TAD reads tender PDFs, detects eight distinct categories of ambiguity, "
        "tries to resolve each flag against IS-code and intra-tender context, and suggests "
        "IS-code-grounded rewrites."
    )

    st.markdown("### The four pipeline stages")
    col = st.columns(4)
    for i, k in enumerate(["parse", "detect_v1", "resolve", "rewrite"]):
        with col[i]:
            e = explain.explain_or_stub(f"stages.{k}")
            st.markdown(f"**{e['title']}**")
            st.caption(e["what"])
            info_popover(f"stages.{k}")

    st.markdown("### The eight ambiguity categories")
    cats = config.ENABLED_CATEGORIES
    cols = st.columns(4)
    for i, c in enumerate(cats):
        with cols[i % 4]:
            with st.container(border=True):
                e = explain.explain_or_stub(f"categories.{c}")
                st.markdown(f"**{e['title']}**")
                st.caption(e["what"])
                info_popover(f"categories.{c}")

    st.markdown("### Why hybrid retrieval (vector + graph)")
    st.write(
        "Categories F, B, I, A, E, J are local — vector retrieval over the tender and IS-codes handles them. "
        "Categories G (priority conflict) and H (numeric inconsistency) are inherently cross-document — vector "
        "retrieval cannot see them. TAD routes G/H to a knowledge graph built from the tender and answers "
        "them from typed nodes (documents, clauses, quantities, priority rules)."
    )

    st.markdown("### The four accuracy guardrails")
    g = [
        ("stages.merge_probe", "G1+G2 — 3-pass ensemble & negative probe"),
        ("stages.judge_citations", "G3 — LLM-as-judge citation verification"),
        ("stages.verify_grounding", "G4 — rewrite grounding verification"),
        ("params.DETECTION_CONFIDENCE_THRESHOLD", "Per-category calibrated thresholds"),
    ]
    cols = st.columns(2)
    for i, (k, label) in enumerate(g):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(explain.explain_or_stub(k)["what"])
                info_popover(k)

    st.markdown("### Metrics at a glance")
    cols = st.columns(3)
    for i, m in enumerate(["metrics.precision", "metrics.recall", "metrics.false_resolution_rate"]):
        with cols[i]:
            with st.container(border=True):
                e = explain.explain_or_stub(m)
                st.markdown(f"**{e['title']}**")
                st.caption(e["benchmark"])
                info_popover(m)

    st.markdown("### Known limitations")
    st.write(
        "- Scanned PDFs without an OCR layer are not supported in this build.\n"
        "- IS-code grounding quality depends on the IS-code PDFs supplied in `is_codes/`. If none are supplied, "
        "resolutions fall back to tender-only retrieval.\n"
        "- Graph extraction is LLM-driven; entity canonicalisation is surface-form-based and will miss some aliases.\n"
        "- The LLM-as-Judge annotation protocol is a mitigation for full double-annotation, not a replacement. Report honestly.\n"
    )
