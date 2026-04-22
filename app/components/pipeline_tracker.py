"""Live pipeline progress tracker with info icons on every stage."""
from __future__ import annotations

import streamlit as st

from .info_icon import info_popover

STAGES = [
    ("parse", "Parse PDFs"),
    ("chunk", "Clause-aware chunking"),
    ("embed", "Embed chunks (text-embedding-004)"),
    ("graph", "Build knowledge graph"),
    ("detect_v1", "Detection pass v1 (positive-led)"),
    ("detect_v2", "Detection pass v2 (open-ended)"),
    ("detect_v3", "Detection pass v3 (adversarial)"),
    ("merge_probe", "Merge + negative-control probe (G1+G2)"),
    ("resolve", "Hybrid resolution"),
    ("judge_citations", "LLM-as-judge citation check (G3)"),
    ("rewrite", "IS-code-grounded rewrite"),
    ("verify_grounding", "Grounding verification (G4)"),
]


def render_tracker(progress: dict[str, float] | None = None, active_stage: str | None = None):
    st.markdown("### Pipeline stages")
    st.caption("Click any (ℹ) to see what the stage does, what it consumes, and what it emits.")
    for key, name in STAGES:
        pct = (progress or {}).get(key, 0.0)
        status_icon = "🟢" if pct >= 1.0 else ("🟡" if key == active_stage else "⚪")
        c1, c2, c3 = st.columns([0.4, 5.0, 0.6])
        with c1:
            st.markdown(f"<div style='font-size:1.1rem'>{status_icon}</div>", unsafe_allow_html=True)
        with c2:
            st.progress(min(1.0, max(0.0, pct)), text=name)
        with c3:
            info_popover(f"stages.{key}")
