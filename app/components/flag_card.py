"""Dual-scored flag card (Prompt-4).

Each card shows: display-name badge, document source, keyword + LLM + combined score gauges with info,
highlighted span, and three expanders (Why flagged / Stage 2 / Stage 3).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import explain
from .info_icon import info_popover, info_tooltip


CATEGORY_COLORS = {
    "F": "#D4A017",
    "B": "#5B8FB9",
    "I": "#B44C7A",
    "A": "#6A994E",
    "E": "#BC4749",
    "G": "#815CA2",
    "H": "#D76A03",
    "J": "#2F7D6A",
}


def _badge(text: str, bg: str) -> str:
    return (
        f"<span style='background:{bg};color:white;padding:2px 8px;border-radius:8px;"
        f"font-size:0.78rem;font-weight:600'>{text}</span>"
    )


def _span_highlight(text: str, start: int, end: int, color: str = "#FDE68A") -> str:
    start = max(0, min(len(text), start))
    end = max(start, min(len(text), end))
    before = text[:start].replace("\n", " ")
    mid = text[start:end].replace("\n", " ")
    after = text[end:].replace("\n", " ")
    return (
        f"<div style='line-height:1.55; font-size:0.95rem'>"
        f"{before}<mark style='background:{color}; padding:1px 3px; border-radius:3px'>{mid}</mark>{after}"
        f"</div>"
    )


def _verdict_label(verdict: str) -> str:
    if not verdict:
        return "Pending"
    return explain.verdict_display(verdict)


def _verdict_color(verdict: str) -> str:
    mapped = explain.verdict_display(verdict)
    if mapped == "Resolved by Context":
        return "#2E7D32"
    if mapped == "Partially Resolved":
        return "#C18A00"
    return "#B00020"


def _score_row(label: str, value: float, key: str):
    c1, c2, c3 = st.columns([3, 2, 0.6])
    with c1:
        st.markdown(f"**{label}**")
    with c2:
        st.progress(min(1.0, max(0.0, float(value or 0))), text=f"{float(value or 0):.2f}")
    with c3:
        info_popover(key)


def render_flag_card(
    flag: dict,
    chunk_text: str,
    chunk_meta: dict | None,
    resolution: dict | None,
    rewrite: dict | None,
):
    cat = flag.get("category", "F")
    cat_color = CATEGORY_COLORS.get(cat, "#444")
    status = flag.get("status", "CONFIRMED")
    verdict = (resolution or {}).get("verdict", "")
    cat_name = explain.category_display(cat)

    with st.container(border=True):
        top = st.columns([5, 2, 0.5])
        with top[0]:
            st.markdown(
                f"{_badge(cat_name, cat_color)} &nbsp; "
                f"{_badge(status, '#2E7D32' if status == 'CONFIRMED' else '#C18A00')}",
                unsafe_allow_html=True,
            )
            # document source
            meta = chunk_meta or {}
            doc_type = meta.get("document_type") or "Other"
            doc_id = meta.get("doc_id") or flag.get("chunk_id", "").split("_")[0]
            page = meta.get("page", "?")
            st.caption(f"Source: **{doc_type}** · `{doc_id}` · page {page}")
        with top[1]:
            st.markdown(
                f"<div style='text-align:right;margin-top:6px'>"
                f"{_badge(_verdict_label(verdict), _verdict_color(verdict))}"
                f"</div>",
                unsafe_allow_html=True,
            )
        with top[2]:
            info_popover(f"categories.{cat}", label="ℹ")

        # Score gauges
        _score_row("Keyword score", float(flag.get("keyword_score", 0)), "scoring.keyword_score")
        _score_row("LLM score", float(flag.get("llm_score", 0)), "scoring.llm_score")
        _score_row(
            f"Combined (α={flag.get('alpha', 0.3):.2f})",
            float(flag.get("combined_score", 0)),
            "scoring.combined_score",
        )

        st.markdown("**Flagged span:**")
        st.markdown(
            _span_highlight(chunk_text, int(flag.get("span_char_start", 0)), int(flag.get("span_char_end", 0))),
            unsafe_allow_html=True,
        )

        with st.expander("🔍 Why was this flagged? (keyword matches + LLM reasoning)"):
            _render_why(flag)
        with st.expander("⚖ Stage 2 — context resolution"):
            _render_resolution(resolution)
        with st.expander("✏ Stage 3 — suggested rewrite"):
            _render_rewrite(rewrite, verdict)


def _render_why(flag: dict):
    matches = flag.get("keyword_matches") or []
    if isinstance(matches, str):
        try:
            import ast
            matches = ast.literal_eval(matches)
        except Exception:
            matches = []
    if matches:
        df = pd.DataFrame(
            [
                {"term": m.get("term"), "weight": m.get("weight"), "position": m.get("position"), "rule": m.get("rule_triggered") or ""}
                for m in matches
            ]
        )
        st.markdown("**Keyword matches (from the category lexicon):**")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No keyword matches — the flag came from the LLM scorer alone.")
    st.markdown("**LLM score + justification:**")
    st.write(flag.get("justification") or "(no justification returned)")
    info_popover("stages.detect", label="ℹ how Stage 1 works")


def _render_resolution(res: dict | None):
    if not res:
        st.info("Resolution pending or skipped.")
        return
    verdict = res.get("verdict", "CONFIRMED_AMBIGUOUS")
    st.markdown(f"**Verdict:** `{_verdict_label(verdict)}`")
    info_popover(f"verdicts.{verdict}", label="ℹ what does this verdict mean?")
    st.markdown("**Adjudicator reasoning:**")
    st.write(res.get("reasoning") or "")
    cited = res.get("cited_context_ids") or []
    stripped = res.get("judge_stripped") or []
    st.markdown(f"**Cited context IDs:** {', '.join(cited) if cited else '—'}")
    if stripped:
        st.warning(f"Judge stripped {len(stripped)} fabricated citation(s): {', '.join(stripped)}")
    retrieved = res.get("retrieved") or []
    if retrieved:
        rows = []
        for r in retrieved:
            m = r.get("meta") or {}
            rows.append({
                "id": r.get("context_id"),
                "doc": m.get("doc_id") or "",
                "doc_type": m.get("document_type") or "",
                "page": m.get("page") or "",
                "score": f"{float(r.get('score', 0)):.2f}",
                "snippet": (r.get("text") or "")[:200].replace("\n", " "),
            })
        st.markdown("**Retrieved contexts (whole tender package):**")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    info_popover("stages.resolve", label="ℹ about Stage 2")
    info_popover("stages.judge_citations", label="ℹ about G3 (citation judge)")


def _render_rewrite(rw: dict | None, verdict: str):
    if explain.verdict_display(verdict) == "Resolved by Context":
        st.info("This flag was Resolved by Context in Stage 2 — no rewrite is needed.")
        return
    if not rw:
        st.info("No rewrite emitted.")
        return
    st.markdown(f"**Status:** `{rw.get('status', '')}`")
    if rw.get("status") == "INSUFFICIENT_GROUNDING":
        st.warning(
            "The rewriter honestly returned INSUFFICIENT_GROUNDING — no fabricated IS/CPWD citation is emitted."
        )
    if rw.get("suggested_text"):
        st.markdown("**Suggested rewrite:**")
        st.code(rw.get("suggested_text"), language="text")
    if rw.get("grounding"):
        st.markdown(f"**Grounding (IS / CPWD):** {', '.join(rw.get('grounding', []))}")
    if rw.get("explanation"):
        st.caption(rw.get("explanation"))
    info_popover("stages.rewrite", label="ℹ about Stage 3")
    info_popover("stages.verify_grounding", label="ℹ about G4 (grounding verification)")
