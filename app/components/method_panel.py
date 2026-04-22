"""About tab — renders the Prompt-4 four-stage methodology with a mermaid diagram."""
from __future__ import annotations

import streamlit as st

from src import config, explain

from .info_icon import info_popover


MERMAID_DIAGRAM = """
flowchart TD
  A[Tender Package Upload] --> B[Document Typing & Selection]
  B --> C[Parse & Chunk<br/><small>selected docs → candidate flags; all docs indexed for retrieval</small>]
  C --> D[Stage 1<br/>Dual-Scoring Detection<br/><small>keyword + LLM → combined → threshold</small>]
  D --> E[Stage 2<br/>Package Context Resolution<br/><small>RAG over whole package → Confirmed / Resolved</small>]
  E -->|Confirmed Ambiguous / Partial| F[Stage 3<br/>Standards-Grounded Rewrite<br/><small>RAG over IS + CPWD → grounded suggestion</small>]
  E -->|Resolved by Context| G[Report shown; no rewrite needed]
"""


def render_method_panel():
    st.markdown("## About this method")
    st.caption(
        "TAD reads a tender package, detects 8 kinds of ambiguity, checks whether the rest of the package "
        "resolves each flag, and suggests a standards-grounded rewrite for the ones it doesn't."
    )

    st.markdown("### The four stages")
    try:
        import streamlit_mermaid as stmd  # type: ignore

        stmd.st_mermaid(MERMAID_DIAGRAM, height="460px")
    except Exception:
        st.code(MERMAID_DIAGRAM, language="text")

    st.markdown("### What each stage does")
    col = st.columns(4)
    for i, k in enumerate(["chunk", "detect", "resolve", "rewrite"]):
        with col[i]:
            e = explain.explain_or_stub(f"stages.{k}")
            st.markdown(f"**{e['title']}**")
            st.caption(e["what"])
            info_popover(f"stages.{k}")

    st.markdown("### The eight ambiguity categories")
    cols = st.columns(4)
    for i, c in enumerate(config.ENABLED_CATEGORIES):
        with cols[i % 4]:
            with st.container(border=True):
                e = explain.explain_or_stub(f"categories.{c}")
                st.markdown(f"**{e['title']}**")
                st.caption(e["what"])
                info_popover(f"categories.{c}")

    st.markdown("### Three verdicts at Stage 2")
    cols = st.columns(3)
    for i, v in enumerate(["CONFIRMED_AMBIGUOUS", "RESOLVED_BY_CONTEXT", "PARTIALLY_RESOLVED"]):
        with cols[i]:
            with st.container(border=True):
                e = explain.explain_or_stub(f"verdicts.{v}")
                st.markdown(f"**{e['title']}**")
                st.caption(e["what"])
                info_popover(f"verdicts.{v}")

    st.markdown("### Accuracy guardrails")
    g = [
        ("stages.detect", "Dual-scoring detector with optional negative-control probe (G2)"),
        ("stages.judge_citations", "G3 — LLM-as-judge citation verification"),
        ("stages.verify_grounding", "G4 — rewrite grounding verification"),
        ("params.DETECTION_THRESHOLD", "Per-category calibrated thresholds"),
    ]
    cols = st.columns(2)
    for i, (k, label) in enumerate(g):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(explain.explain_or_stub(k)["what"])
                info_popover(k)

    st.markdown("### Key metrics")
    cols = st.columns(3)
    for i, m in enumerate(["metrics.precision", "metrics.resolved_by_context_rate", "metrics.false_resolution_rate"]):
        with cols[i]:
            with st.container(border=True):
                e = explain.explain_or_stub(m)
                st.markdown(f"**{e['title']}**")
                st.caption(e["benchmark"])
                info_popover(m)

    st.markdown("### Known limitations (report honestly)")
    st.write(
        "- Scanned PDFs without an OCR layer are not supported.\n"
        "- IS-code / CPWD grounding quality depends on the standards PDFs ingested via src.is_code_ingest.\n"
        "- Entity canonicalisation in the graph is surface-form-based and misses some aliases.\n"
        "- The LLM-as-Judge annotation protocol is a mitigation for full double-annotation, not a replacement."
    )

    st.markdown("### Design changes vs the initial build")
    st.write(
        "- **Package, not a single document.** Users upload the whole tender package; Stage 2 retrieves across the whole package.\n"
        "- **Dual-scoring, not 3-pass ensemble.** Each chunk gets a keyword score + a single LLM score; combined above threshold → flagged. The legacy ensemble is preserved behind `USE_LEGACY_ENSEMBLE` for ablation.\n"
        "- **Two-stage RAG.** Stage 2 retrieves from the tender package to check whether the flag is real; Stage 3 retrieves from IS + CPWD to ground a rewrite.\n"
        "- **Intuitive category names.** Letter codes are internal IDs only; every UI surface shows display names."
    )
