"""Phase-5 human spot-check annotation page for the LLM-as-Judge protocol."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src import explain

from .info_icon import info_popover, info_tooltip

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DIR = ROOT / "gold"
QUEUE = GOLD_DIR / "annotation_queue.jsonl"
OUT = GOLD_DIR / "tender_ambiguity.jsonl"


def _load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    rows = []
    for ln in QUEUE.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return rows


def render_annotation_page():
    st.markdown("## Annotation — Phase 5 human spot-check")
    st.caption(
        "Review the LLM-as-Judge boundary bucket. Tick or cross each item; anything "
        "marked ticked lands in `gold/tender_ambiguity.jsonl` as part of the final gold set."
    )
    info_popover("annotation_protocol.phase_5_human", label="ℹ what this phase does")

    queue = _load_queue()
    if not queue:
        st.info(
            "`gold/annotation_queue.jsonl` is empty. Run the annotation protocol first:\n\n"
            "```\npython -m src.annotation_protocol --run-id <latest_run>\n```"
        )
        return

    st.session_state.setdefault("gold_phase5", {})
    gold = st.session_state["gold_phase5"]

    hit = miss = 0
    for i, item in enumerate(queue):
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 2, 2])
            with c1:
                st.markdown(
                    f"**{explain.category_display(item.get('category') or 'F')}** — "
                    f"`{(item.get('span_text') or '')[:100]}`"
                )
                st.caption((item.get("chunk_text") or "")[:500])
                if item.get("judge_rationales"):
                    st.caption(f"Judge: {item['judge_rationales'][:240]}")
            with c2:
                options = ["(not decided)", "TRUE_POSITIVE", "FALSE_POSITIVE", "WRONG_CATEGORY"]
                default = gold.get(item.get("id") or str(i), {}).get("decision", "(not decided)")
                idx = options.index(default) if default in options else 0
                dec = st.selectbox(
                    f"decision {i}",
                    options,
                    index=idx,
                    key=f"ann_q_{i}",
                    label_visibility="collapsed",
                )
                if dec != "(not decided)":
                    gold[item.get("id") or str(i)] = {"decision": dec, "item": item}
                    if dec == "TRUE_POSITIVE":
                        hit += 1
                    else:
                        miss += 1
            with c3:
                info_popover(
                    f"categories.{item.get('category') or 'F'}", label="ℹ category"
                )

    m1, m2 = st.columns(2)
    m1.metric("Ticked as TRUE_POSITIVE", hit, help=info_tooltip("annotation_protocol.phase_5_human"))
    m2.metric("Rejected / re-categorised", miss)

    if gold:
        rows = []
        for k, v in gold.items():
            item = v["item"]
            rows.append(
                {
                    "flag_id": k,
                    "category": item.get("category"),
                    "category_name": explain.category_display(item.get("category") or "F"),
                    "span_text": item.get("span_text"),
                    "decision": v["decision"],
                    "source": "human_spot_check",
                }
            )
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if st.button("Persist ticked items to gold/tender_ambiguity.jsonl"):
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with OUT.open("a", encoding="utf-8") as f:
                for r in rows:
                    if r["decision"] == "TRUE_POSITIVE":
                        f.write(json.dumps(r) + "\n")
            st.success(f"Appended {sum(1 for r in rows if r['decision']=='TRUE_POSITIVE')} items to {OUT.name}")
