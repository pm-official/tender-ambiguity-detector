"""Tender picker — reads tenders/real/*/manifest.yaml and offers pre-staged demo packages."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
TENDERS = ROOT / "tenders" / "real"


def list_tenders() -> list[dict]:
    out = []
    if not TENDERS.exists():
        return out
    for d in sorted(TENDERS.iterdir()):
        mf = d / "manifest.yaml"
        if not mf.exists():
            continue
        try:
            data = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        data["_dir"] = d
        out.append(data)
    return out


def pick_tender_widget() -> Optional[dict]:
    tenders = list_tenders()
    if not tenders:
        st.caption("No pre-staged tender packages. Upload below, or run `python scripts/make_synthetic_package.py`.")
        return None

    labels = []
    for t in tenders:
        badge = "SYNTHETIC" if t.get("synthetic") else "REAL"
        v = t.get("value_crore")
        vstr = f" · Rs. {v:.1f} cr" if isinstance(v, (int, float)) and v else ""
        labels.append(f"[{badge}] {t.get('short_name') or t.get('package_id')}{vstr} - {len(t.get('documents') or [])} docs")

    idx = st.selectbox("Pre-staged tender packages", range(len(labels)), format_func=lambda i: labels[i])
    return tenders[idx]


def render_demo_banner(manifest: dict | None) -> None:
    if not manifest:
        return
    synthetic = bool(manifest.get("synthetic"))
    bg = "#FFECB3" if synthetic else "#D0E8FF"
    fg = "#7A4F01" if synthetic else "#0A3D66"
    label = "SYNTHETIC demo package" if synthetic else "Public-procurement demo package"
    note = (
        "Labelled synthetic; no empirical claims made on this run."
        if synthetic
        else "No bidder information is included."
    )
    st.markdown(
        f"<div style='background:{bg};color:{fg};padding:8px 12px;border-radius:6px;"
        f"font-size:0.88rem;margin:4px 0 12px 0'>"
        f"<b>{label}.</b> {note} See docs/licensing_and_attribution.md."
        f"</div>",
        unsafe_allow_html=True,
    )
