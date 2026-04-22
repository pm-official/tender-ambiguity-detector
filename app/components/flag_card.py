"""Flag card: one per confirmed flag, with 3 expanders + ensemble panel + resolution + rewrite."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import explain
from .info_icon import info_popover, info_tooltip


CATEGORY_COLORS = {
    "F": "#D4A017", "B": "#5B8FB9", "I": "#B44C7A", "A": "#6A994E",
    "E": "#BC4749", "G": "#815CA2", "H": "#D76A03", "J": "#2F7D6A",
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


def render_flag_card(flag: dict, chunk_text: str, resolution: dict | None, rewrite: dict | None):
    cat = flag["category"]
    cat_color = CATEGORY_COLORS.get(cat, "#444")
    status = flag.get("status", "CONFIRMED")
    agreement = float(flag.get("agreement_rate", 0))
    mean_conf = float(flag.get("mean_confidence", 0))

    with st.container(border=True):
        top = st.columns([4.5, 1, 1, 1, 0.5])
        with top[0]:
            st.markdown(
                f"{_badge(f'{cat} — ' + explain.get('categories.' + cat + '.title', cat), cat_color)} "
                f"&nbsp; {_badge(status, '#2E7D32' if status == 'CONFIRMED' else '#C18A00')}",
                unsafe_allow_html=True,
            )
        with top[1]:
            st.metric("Agreement", f"{agreement*100:.0f}%", help=info_tooltip("metrics.agreement_rate"))
        with top[2]:
            st.metric("Confidence", f"{mean_conf:.2f}", help=info_tooltip("metrics.mean_confidence"))
        with top[3]:
            verdict = (resolution or {}).get("verdict", "PENDING")
            v_color = {"RESOLVED": "#2E7D32", "PARTIALLY_RESOLVED": "#C18A00", "UNRESOLVED": "#B00020"}.get(verdict, "#555")
            st.markdown(f"<div style='text-align:center;margin-top:8px'>{_badge(verdict, v_color)}</div>", unsafe_allow_html=True)
        with top[4]:
            info_popover(f"categories.{cat}", label="ℹ")

        st.markdown("**Span (highlighted in its clause):**")
        st.markdown(
            _span_highlight(chunk_text, int(flag.get("span_char_start", 0)), int(flag.get("span_char_end", 0))),
            unsafe_allow_html=True,
        )

        # Three canonical expanders
        with st.expander("🔍 Why was this flagged? (ensemble + probe)"):
            _render_ensemble(flag)

        with st.expander("⚖ How was it adjudicated? (retrieval + judge)"):
            _render_resolution(resolution)

        with st.expander("✏ Suggested rewrite (IS-code grounded)"):
            _render_rewrite(rewrite)


def _render_ensemble(flag: dict):
    passes = flag.get("passes") or []
    if not isinstance(passes, list):
        try:
            import ast
            passes = ast.literal_eval(passes)
        except Exception:
            passes = []
    cols = st.columns(3)
    seen = {p.get("pass_id") for p in passes if isinstance(p, dict)}
    for i, variant in enumerate(("v1", "v2", "v3")):
        with cols[i]:
            if variant in seen:
                match = next((p for p in passes if isinstance(p, dict) and p.get("pass_id") == variant), None)
                st.markdown(f"**Pass {variant} ✅**")
                if match:
                    st.caption(f"conf={float(match.get('confidence',0)):.2f}")
                    st.write(match.get("justification", ""))
            else:
                st.markdown(f"**Pass {variant} ❌** — did not flag")
            info_popover(f"stages.detect_{variant}", label="ℹ explain this pass")

    probe = flag.get("negative_probe")
    st.markdown("---")
    st.markdown("**Negative-control probe (G2):**")
    if probe and isinstance(probe, dict):
        disagrees = probe.get("disagrees")
        mark = "⚠ probe disagreed" if disagrees else "✅ probe agreed"
        st.markdown(f"{mark} — *{probe.get('reason','')}*")
    else:
        st.caption("(no probe run for this category)")
    info_popover("stages.merge_probe", label="ℹ about G1+G2")


def _render_resolution(res: dict | None):
    if not res:
        st.info("Resolution pending or skipped.")
        return
    verdict = res.get("verdict", "UNRESOLVED")
    st.markdown(f"**Verdict:** `{verdict}`")
    info_popover(f"verdicts.{verdict}", label="ℹ what does this verdict mean?")
    st.markdown("**Adjudicator reasoning:**")
    st.write(res.get("reasoning", ""))
    cited = res.get("cited_context_ids") or []
    stripped = res.get("judge_stripped") or []
    st.markdown(f"**Cited context IDs:** {', '.join(cited) if cited else '—'}")
    if stripped:
        st.warning(f"Judge stripped {len(stripped)} fabricated citation(s): {', '.join(stripped)}")
    retrieved = res.get("retrieved") or []
    if retrieved:
        st.markdown("**Retrieved contexts:**")
        rows = []
        for r in retrieved:
            rows.append({
                "id": r.get("context_id"),
                "source": r.get("source"),
                "score": f"{float(r.get('score',0)):.2f}",
                "snippet": (r.get("text") or "")[:200].replace("\n", " "),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    info_popover("stages.resolve", label="ℹ about Stage 2")
    info_popover("stages.judge_citations", label="ℹ about G3 (citation judge)")


def _render_rewrite(rw: dict | None):
    if not rw:
        st.info("No rewrite emitted (flag may be RESOLVED or rewriter skipped).")
        return
    st.markdown(f"**Status:** `{rw.get('status','')}`")
    if rw.get("status") == "INSUFFICIENT_GROUNDING":
        st.warning("The rewriter honestly returned INSUFFICIENT_GROUNDING — no fabricated IS-code citation is emitted.")
    if rw.get("suggested_text"):
        st.markdown("**Suggested rewrite:**")
        st.code(rw.get("suggested_text",""), language="text")
    if rw.get("grounding"):
        st.markdown(f"**Grounding:** {', '.join(rw.get('grounding', []))}")
    st.caption(rw.get("explanation",""))
    info_popover("stages.rewrite", label="ℹ about Stage 3")
    info_popover("stages.verify_grounding", label="ℹ about G4 (grounding verification)")
