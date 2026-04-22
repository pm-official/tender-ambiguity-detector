"""Interactive knowledge-graph explorer powered by pyvis."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src import explain
from .info_icon import info_popover

COLORS = {
    "DOCUMENT": "#1F4E79",
    "CLAUSE": "#4B86B4",
    "ENTITY": "#8AB17D",
    "QUANTITY": "#E9A23B",
    "PRIORITY_RULE": "#B05A7A",
}


def render_graph_panel(graph_json: dict | None):
    st.markdown("## Graph Explorer")
    st.caption("Visualise the tender knowledge graph — used for G/H detection.")

    if not graph_json or not graph_json.get("nodes"):
        st.info("No graph artifact found for this run. Run the pipeline first on the Analyse tab.")
        return

    legend = explain.get("graph_legend") or {}
    with st.expander("Legend — node kinds, edges, colours"):
        st.markdown("**Node kinds**")
        for k, v in (legend.get("nodes") or {}).items():
            c = COLORS.get(k, "#555")
            st.markdown(
                f"<span style='display:inline-block;width:12px;height:12px;background:{c};"
                f"border-radius:3px;margin-right:8px'></span>**{k}** — {v.get('what','')}",
                unsafe_allow_html=True,
            )
        st.markdown("**Edge kinds**")
        for k, v in (legend.get("edges") or {}).items():
            st.markdown(f"- **{k}** — {v.get('what','')}")

    try:
        from pyvis.network import Network
    except Exception as e:
        st.error(f"pyvis unavailable: {e}")
        return

    net = Network(height="560px", width="100%", bgcolor="#FFFFFF", font_color="#111", directed=True)
    net.toggle_physics(True)

    nodes = graph_json["nodes"]
    edges = graph_json.get("edges", [])
    for n in nodes:
        kind = n.get("kind", "ENTITY")
        color = COLORS.get(kind, "#888")
        label_src = (
            n.get("title") or n.get("canonical") or n.get("name") or n.get("clause_hint") or n.get("id", "")
        )
        label = (str(label_src) or n.get("id", ""))[:50]
        tip = f"{kind}: {label}"
        if kind == "CLAUSE" and n.get("text"):
            tip = tip + "\n" + n["text"][:200]
        net.add_node(n["id"], label=label, color=color, title=tip, shape="dot")

    node_ids = {n["id"] for n in nodes}
    for e in edges:
        if e["source"] in node_ids and e["target"] in node_ids:
            color = "#CC2936" if e.get("kind") == "INCONSISTENT_WITH" else "#BBB"
            dashed = e.get("kind") == "INCONSISTENT_WITH"
            net.add_edge(e["source"], e["target"], title=e.get("kind", ""), color=color, dashes=dashed)

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        try:
            net.save_graph(f.name)
            html = Path(f.name).read_text(encoding="utf-8")
            components.html(html, height=600, scrolling=False)
        except Exception as e:
            st.error(f"Could not render graph: {e}")

    # Quick stats
    counts: dict[str, int] = {}
    for n in nodes:
        counts[n.get("kind", "?")] = counts.get(n.get("kind", "?"), 0) + 1
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Documents", counts.get("DOCUMENT", 0))
    c2.metric("Clauses", counts.get("CLAUSE", 0))
    c3.metric("Entities", counts.get("ENTITY", 0))
    c4.metric("Quantities", counts.get("QUANTITY", 0))
    c5.metric("Priority rules", counts.get("PRIORITY_RULE", 0))
    info_popover("graph_legend.nodes.DOCUMENT", label="ℹ what is each node kind?")
