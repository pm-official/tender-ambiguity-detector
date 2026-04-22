"""Standards catalog tab — renders the IS-code / CPWD corpus with source URLs, license notes, SHA-256."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

from .info_icon import info_popover, info_tooltip

ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = ROOT / "standards" / "metadata" / "catalog.yaml"


def render_standards_catalog():
    st.markdown("## Standards catalog")
    st.caption(
        "Every IS-code / CPWD PDF that Stage 3 can cite when it rewrites a flagged clause. "
        "BIS and CPWD retain copyright; TAD reads the text at retrieval time and never "
        "republishes source text. See the licensing doc for attribution."
    )
    c1, _ = st.columns([1, 5])
    with c1:
        info_popover("scoring.combined_score", label="ℹ how is this corpus used?")

    if not CATALOG_PATH.exists():
        st.info("Standards catalog not found. Run `python scripts/download_standards.py` locally.")
        return

    data = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    entries = data.get("entries") or []
    ok = sum(1 for e in entries if e.get("status") == "OK")
    missing = sum(1 for e in entries if e.get("status") == "MISSING")
    planned = sum(1 for e in entries if e.get("status") == "PLANNED")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", len(entries))
    m2.metric("Ingested (OK)", ok)
    m3.metric("Missing", missing)
    m4.metric("Planned", planned)

    tabs = st.tabs(["Priority 1 — IS codes", "Priority 2 — CPWD", "Priority 3 — Optional"])
    for tab, prio in zip(tabs, [1, 2, 3]):
        with tab:
            rows = [e for e in entries if e.get("priority") == prio]
            if not rows:
                st.caption("(no entries at this tier)")
                continue
            for e in rows:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1.3])
                    with col1:
                        st.markdown(f"**{e.get('code')}** — {e.get('title')}")
                        st.caption(f"{e.get('year')} · {e.get('topic') or ''}")
                    with col2:
                        status = e.get("status", "PLANNED")
                        colour = {"OK": "#2E7D32", "MISSING": "#B00020"}.get(status, "#888")
                        st.markdown(
                            f"<span style='background:{colour};color:white;padding:2px 8px;"
                            f"border-radius:6px;font-size:0.78rem;font-weight:600'>{status}</span>",
                            unsafe_allow_html=True,
                        )
                        if e.get("pages"):
                            st.caption(f"{e.get('pages')} pages · {round((e.get('bytes') or 0)/1e6, 1)} MB")
                    with col3:
                        st.link_button("Source", e.get("source_url") or "#", use_container_width=True)
                    with st.expander("Licensing and hash"):
                        st.write(e.get("license_note") or "")
                        st.caption(f"SHA-256: `{e.get('sha256_expected') or '—'}`")
                        if e.get("archive_fallback"):
                            st.caption(f"Archive fallback: {e.get('archive_fallback')}")

    st.markdown("---")
    st.caption(
        "Full attribution: Carl Malamud / Public.Resource.Org (BIS mirror), Bureau of Indian "
        "Standards, and Government of India / CPWD. See `docs/licensing_and_attribution.md`."
    )
