"""The universal (ℹ) info icon. Every number/label in the app calls this.

Uses Streamlit's help parameter + a popover for a richer 'title / what / why / how / benchmark / example' card.
"""
from __future__ import annotations

import streamlit as st

from src import explain


def info_tooltip(key_path: str) -> str:
    """Return a tooltip string for st.metric(..., help=...) / st.selectbox(..., help=...)."""
    e = explain.explain_or_stub(key_path)
    parts = []
    if e["what"]:
        parts.append(f"**What:** {e['what']}")
    if e["why"]:
        parts.append(f"**Why:** {e['why']}")
    if e["how"]:
        parts.append(f"**How:** {e['how']}")
    if e["benchmark"]:
        parts.append(f"**Benchmark:** {e['benchmark']}")
    if e["example"]:
        parts.append(f"**Example:** {e['example']}")
    if not parts:
        return key_path
    return "\n\n".join(parts)


def info_popover(key_path: str, label: str = "ℹ"):
    """Render a popover button that opens the full explanation card. Use inline beside a number."""
    e = explain.explain_or_stub(key_path)
    with st.popover(label, help=f"Explain: {e['title']}"):
        st.markdown(f"### {e['title']}")
        if e["what"]:
            st.markdown(f"**What** — {e['what']}")
        if e["why"]:
            st.markdown(f"**Why it matters** — {e['why']}")
        if e["how"]:
            st.markdown(f"**How it is calculated** — {e['how']}")
        if e["benchmark"]:
            st.markdown(f"**Benchmark / band** — {e['benchmark']}")
        if e["example"]:
            st.markdown(f"**Worked example** — {e['example']}")
        st.caption(f"Source key: `{key_path}`")


def number_with_info(label: str, value, key_path: str, *, fmt: str = "{}"):
    """Render a labelled number with an info popover beside it."""
    c1, c2, c3 = st.columns([3, 1.5, 0.5])
    with c1:
        st.markdown(f"**{label}**")
    with c2:
        if isinstance(value, float):
            st.markdown(f"`{value:.3f}`")
        else:
            st.markdown(f"`{fmt.format(value)}`")
    with c3:
        info_popover(key_path)


def metric_with_info(label: str, value, key_path: str, *, fmt: str | None = None, delta=None):
    """st.metric + info popover beside it."""
    c1, c2 = st.columns([5, 1])
    with c1:
        if fmt and isinstance(value, (int, float)):
            st.metric(label, fmt.format(value), delta=delta, help=info_tooltip(key_path))
        else:
            st.metric(label, value, delta=delta, help=info_tooltip(key_path))
    with c2:
        info_popover(key_path)
