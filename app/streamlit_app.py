"""Tender Ambiguity Detector — Streamlit entry point."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# allow `from src import ...`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.components.flag_card import render_flag_card  # noqa: E402
from app.components.graph_panel import render_graph_panel  # noqa: E402
from app.components.info_icon import info_popover, info_tooltip  # noqa: E402
from app.components.method_panel import render_method_panel  # noqa: E402
from app.components.pipeline_tracker import render_tracker  # noqa: E402
from src import config, explain  # noqa: E402
from src.pipeline import list_runs, load_pipeline_result, run_pipeline  # noqa: E402

st.set_page_config(
    page_title="Tender Ambiguity Detector",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Global header
# ---------------------------------------------------------------------------


def _onboarding_tour():
    steps = [
        ("Welcome", "TAD reads Indian construction tender PDFs and flags 8 categories of ambiguity. Every number has an (ℹ) icon — click any of them to see what it means."),
        ("Upload a PDF", "Go to **Analyse**. Upload a tender PDF (or pick a sample). Hit Run."),
        ("Read the flags", "Each flag shows a highlighted span, a category badge, an agreement-rate, and a confidence. The category badge's ℹ opens the definition."),
        ("Open a flag card", "Each flag has 3 expanders: *Why flagged* (3-pass ensemble + probe), *How adjudicated* (retrieval + judge), *Suggested rewrite* (IS-code grounded)."),
        ("Check Metrics", "The Metrics tab shows per-category precision/recall/F1 with worked examples. The false-resolution-rate is the safety metric."),
        ("About this method", "For a quick read of how everything fits together, visit the About tab."),
    ]
    st.session_state.setdefault("tour_step", 0)
    step = st.session_state["tour_step"]
    step = max(0, min(step, len(steps) - 1))
    with st.container(border=True):
        t, b = steps[step]
        st.markdown(f"### {step+1}/{len(steps)} — {t}")
        st.write(b)
        c1, c2, c3 = st.columns([1, 1, 5])
        with c1:
            if st.button("Previous", disabled=step == 0, key="tour_prev"):
                st.session_state["tour_step"] = step - 1
                st.rerun()
        with c2:
            if st.button("Next", disabled=step == len(steps) - 1, key="tour_next"):
                st.session_state["tour_step"] = step + 1
                st.rerun()
        with c3:
            if st.button("Close tour", key="tour_close"):
                st.session_state["show_tour"] = False
                st.rerun()


def _glossary_modal():
    with st.expander("📚 Glossary of terms used in this app", expanded=True):
        all_expl = explain.all_explanations()
        groups = {
            "Categories": all_expl.get("categories", {}),
            "Verdicts": all_expl.get("verdicts", {}),
            "Metrics": all_expl.get("metrics", {}),
            "Stages": all_expl.get("stages", {}),
            "Parameters": all_expl.get("params", {}),
        }
        for gname, items in groups.items():
            st.markdown(f"### {gname}")
            for k, v in items.items():
                if not isinstance(v, dict):
                    continue
                st.markdown(f"- **{v.get('title', k)}** — {v.get('what','')}")


def _header():
    st.markdown(
        """
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:4px 0 8px 0;border-bottom:1px solid #E6E8EB;margin-bottom:10px'>
          <div>
            <div style='font-size:1.35rem;font-weight:700;color:#1F4E79'>📑 Tender Ambiguity Detector</div>
            <div style='color:#555;font-size:0.88rem'>Self-explaining detection, hybrid retrieval, IS-code-grounded rewrites.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 8])
    with c1:
        if st.button("❓ What is this?", help="Start a 6-step tour"):
            st.session_state["show_tour"] = True
    with c2:
        if st.button("📚 Glossary"):
            st.session_state["show_glossary"] = not st.session_state.get("show_glossary", False)
    if st.session_state.get("show_tour"):
        _onboarding_tour()
    if st.session_state.get("show_glossary"):
        _glossary_modal()


def _sidebar():
    with st.sidebar:
        st.markdown("### Run configuration")

        st.markdown("**Enabled categories**")
        st.caption("Pick which ambiguity categories the detector will run.")
        cats_enabled = []
        cols = st.columns(4)
        for i, cat in enumerate(config.ENABLED_CATEGORIES):
            with cols[i % 4]:
                on = st.checkbox(cat, value=True, key=f"en_{cat}", help=info_tooltip(f"categories.{cat}"))
                if on:
                    cats_enabled.append(cat)
        st.session_state["enabled_categories"] = cats_enabled

        st.markdown("---")
        st.markdown("**Guardrails**")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.session_state["disable_neg_probe"] = not st.checkbox(
                "G2 — negative-control probe", value=True, help=info_tooltip("stages.merge_probe")
            )
        with c2:
            info_popover("stages.merge_probe")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.session_state["disable_citation_judge"] = not st.checkbox(
                "G3 — citation judge", value=True, help=info_tooltip("stages.judge_citations")
            )
        with c2:
            info_popover("stages.judge_citations")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.session_state["disable_ground_verify"] = not st.checkbox(
                "G4 — grounding verification", value=True, help=info_tooltip("stages.verify_grounding")
            )
        with c2:
            info_popover("stages.verify_grounding")

        st.markdown("---")
        st.markdown("**Per-category thresholds**")
        st.caption("Calibration-tuned minima. Run calibration to update these.")
        for cat in config.ENABLED_CATEGORIES:
            cc1, cc2 = st.columns([5, 1])
            with cc1:
                st.slider(
                    f"Threshold {cat}",
                    0.0,
                    1.0,
                    value=float(config.DETECTION_CONFIDENCE_THRESHOLD.get(cat, 0.55)),
                    step=0.05,
                    key=f"thr_{cat}",
                )
            with cc2:
                info_popover("params.DETECTION_CONFIDENCE_THRESHOLD", label="ℹ")

        st.markdown("---")
        st.markdown("**Model configuration**")
        with st.expander("Models in use"):
            for k, v in config.dump().items():
                st.markdown(f"- `{k}` = `{v}`")
            info_popover("params.DETECTION_MODEL", label="ℹ detection model")
            info_popover("params.ADJUDICATION_MODEL", label="ℹ adjudication model")

        st.markdown("---")
        st.caption("TAD — M.Tech thesis project, IIT Bombay.")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


def _analyse_tab():
    st.markdown("### Analyse a tender")
    st.caption(
        "Upload a tender PDF (or pick a sample), then click **Run pipeline**. "
        "Every (ℹ) opens a full explanation."
    )

    # Sample picker
    sample_dir = Path(__file__).resolve().parent.parent / "data" / "sample_tenders"
    samples = sorted(sample_dir.glob("*.pdf")) if sample_dir.exists() else []

    c1, c2 = st.columns([3, 2])
    with c1:
        uploaded = st.file_uploader("Upload PDF(s)", type=["pdf"], accept_multiple_files=True)
    with c2:
        sample_name = st.selectbox(
            "…or pick a sample",
            options=["— none —"] + [p.name for p in samples],
            help="Samples are included in data/sample_tenders/.",
        )

    cc1, cc2 = st.columns([1, 5])
    with cc1:
        run_btn = st.button("▶ Run pipeline", type="primary", use_container_width=True)
    with cc2:
        st.caption("Runs parse → chunk → embed → graph → 3-pass detection → resolve → rewrite.")

    tracker_placeholder = st.container()
    progress_placeholder = st.empty()

    if run_btn:
        pdfs: list[Path] = []
        staging = Path(__file__).resolve().parent.parent / "output" / "_uploads"
        staging.mkdir(parents=True, exist_ok=True)
        if uploaded:
            for u in uploaded:
                p = staging / u.name
                p.write_bytes(u.read())
                pdfs.append(p)
        if sample_name and sample_name != "— none —":
            pdfs.append(sample_dir / sample_name)
        if not pdfs:
            st.warning("Upload at least one PDF or pick a sample.")
        else:
            progress = {}
            active = {"stage": None, "msg": ""}

            def _cb(stage, pct, msg):
                progress[stage] = max(pct, progress.get(stage, 0.0))
                active["stage"] = stage
                active["msg"] = msg
                with tracker_placeholder:
                    render_tracker(progress, active_stage=stage)
                progress_placeholder.info(f"{stage}: {msg}")

            try:
                result = run_pipeline(
                    pdfs,
                    enabled_categories=st.session_state.get("enabled_categories"),
                    disable_neg_probe=st.session_state.get("disable_neg_probe", False),
                    disable_citation_judge=st.session_state.get("disable_citation_judge", False),
                    disable_ground_verify=st.session_state.get("disable_ground_verify", False),
                    progress_cb=_cb,
                )
                progress_placeholder.success(
                    f"Pipeline complete in {result.elapsed_seconds:.1f}s — run_id = {result.run_id}"
                )
                st.session_state["last_run_id"] = result.run_id
            except Exception as e:
                progress_placeholder.error(f"Pipeline failed: {e}")
                st.exception(e)

    st.markdown("---")
    # Run selector
    runs = list_runs()
    if not runs:
        st.info("No completed runs yet. Run the pipeline above.")
        return
    default_run = st.session_state.get("last_run_id") or runs[0]
    if default_run not in runs:
        default_run = runs[0]
    run_id = st.selectbox("Pick a run to view", runs, index=runs.index(default_run))
    data = load_pipeline_result(run_id)
    st.session_state["current_run_data"] = data

    result = data.get("result", {})
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Chunks", result.get("n_chunks", 0), help=info_tooltip("stages.chunk"))
    m2.metric("Confirmed", result.get("n_flags_confirmed", 0), help=info_tooltip("metrics.agreement_rate"))
    m3.metric("Review queue", result.get("n_flags_review", 0), help=info_tooltip("metrics.agreement_rate"))
    m4.metric("Resolutions", result.get("n_resolutions", 0), help=info_tooltip("stages.resolve"))
    m5.metric("Rewrites", result.get("n_rewrites", 0), help=info_tooltip("stages.rewrite"))

    # filter bar
    flags = data.get("flags", []) or []
    chunks_map = {c.get("id"): c for c in (data.get("chunks") or [])}
    resolutions_map = {r.get("flag_id"): r for r in (data.get("resolutions") or [])}
    rewrites_map = {r.get("flag_id"): r for r in (data.get("rewrites") or [])}

    filt_cols = st.columns([2, 2, 2, 3])
    with filt_cols[0]:
        cat_filter = st.multiselect("Categories", sorted({f.get("category") for f in flags}), default=None)
    with filt_cols[1]:
        status_filter = st.multiselect("Status", ["CONFIRMED", "REVIEW_QUEUE"], default=["CONFIRMED"])
    with filt_cols[2]:
        verdict_filter = st.multiselect(
            "Verdict",
            ["RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED", "(no resolution)"],
            default=None,
        )
    with filt_cols[3]:
        sort_by = st.selectbox("Sort by", ["mean_confidence", "agreement_rate", "category"], index=0)

    def _pred(f):
        if cat_filter and f.get("category") not in cat_filter:
            return False
        if status_filter and f.get("status") not in status_filter:
            return False
        if verdict_filter:
            v = resolutions_map.get(f.get("id"), {}).get("verdict", "(no resolution)")
            if v not in verdict_filter:
                return False
        return True

    selected_flags = [f for f in flags if _pred(f)]
    if sort_by == "category":
        selected_flags.sort(key=lambda x: x.get("category", "ZZ"))
    else:
        selected_flags.sort(key=lambda x: x.get(sort_by, 0), reverse=True)

    st.caption(f"Showing {len(selected_flags)} / {len(flags)} flags")
    for f in selected_flags[:200]:
        chunk_text = (chunks_map.get(f.get("chunk_id")) or {}).get("text", "") or ""
        render_flag_card(f, chunk_text, resolutions_map.get(f.get("id")), rewrites_map.get(f.get("id")))


def _annotate_tab():
    st.markdown("### Annotate (gold-set spot-check)")
    st.caption(
        "This is Phase 5 of the annotation protocol. Review the auto-selected queue and confirm / reject each flag. "
        "Your verdicts override the LLM-as-Judge vote."
    )
    info_popover("annotation_protocol.phase_5_human", label="ℹ about the annotation protocol")

    data = st.session_state.get("current_run_data")
    if not data or not data.get("flags"):
        st.info("Run the pipeline first (Analyse tab).")
        return

    flags = data.get("flags") or []
    chunks_map = {c.get("id"): c for c in (data.get("chunks") or [])}

    st.session_state.setdefault("gold_labels", {})
    gold = st.session_state["gold_labels"]

    for i, f in enumerate(flags[:60]):
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                st.markdown(
                    f"**{f.get('category')}** — `{f.get('span_text','')[:80]}`  "
                    f"(conf={float(f.get('mean_confidence',0)):.2f}, agree={float(f.get('agreement_rate',0))*100:.0f}%)"
                )
                chk = chunks_map.get(f.get("chunk_id"))
                if chk:
                    st.caption(chk.get("text", "")[:260])
            with c2:
                options = ["(not decided)", "TRUE_POSITIVE", "FALSE_POSITIVE", "WRONG_CATEGORY", "UNCERTAIN"]
                cur = gold.get(f.get("id"), {}).get("decision", "(not decided)")
                idx = options.index(cur) if cur in options else 0
                dec = st.selectbox(f"Label for flag {i+1}", options, index=idx, key=f"ann_{f.get('id')}", label_visibility="collapsed")
                if dec != "(not decided)":
                    gold[f.get("id")] = {"decision": dec, "flag": f}
            with c3:
                st.markdown(" ")
                info_popover(f"categories.{f.get('category')}", label="ℹ category definition")

    # export
    if gold:
        df = pd.DataFrame(
            {
                "flag_id": k,
                "category": v["flag"].get("category"),
                "span_text": v["flag"].get("span_text"),
                "decision": v["decision"],
            }
            for k, v in gold.items()
        )
        st.markdown("**Your gold annotations so far:**")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇ Download gold CSV", df.to_csv(index=False), file_name="gold_annotations.csv"
        )


def _metrics_tab():
    st.markdown("### Metrics")
    st.caption("Every metric has an (ℹ) button that opens what/why/how/benchmark/example.")

    data = st.session_state.get("current_run_data")
    if not data:
        st.info("Run the pipeline first (Analyse tab) and pick a run on the Analyse tab.")
        return

    flags = data.get("flags", []) or []
    resolutions = data.get("resolutions", []) or []

    st.markdown("#### Flag distribution")
    per_cat = {}
    for f in flags:
        if f.get("status") != "CONFIRMED":
            continue
        per_cat[f.get("category")] = per_cat.get(f.get("category"), 0) + 1
    if per_cat:
        df = pd.DataFrame({"category": list(per_cat.keys()), "count": list(per_cat.values())}).sort_values("category")
        st.bar_chart(df.set_index("category"))
    else:
        st.caption("No confirmed flags in this run.")

    st.markdown("#### Verdict distribution")
    verdict_counts = {"RESOLVED": 0, "PARTIALLY_RESOLVED": 0, "UNRESOLVED": 0}
    for r in resolutions:
        v = r.get("verdict")
        if v in verdict_counts:
            verdict_counts[v] += 1
    cols = st.columns(3)
    for i, (v, n) in enumerate(verdict_counts.items()):
        with cols[i]:
            st.metric(v, n, help=info_tooltip(f"verdicts.{v}"))
            info_popover(f"verdicts.{v}")

    st.markdown("#### Safety metric — false-resolution rate")
    st.caption(
        "Computed only when you provide audits (in the Annotate tab). "
        "Until then we show N/A and leave the band blank. This is intentional honesty — "
        "see the info icon."
    )
    c1, c2 = st.columns([5, 1])
    with c1:
        st.metric("false_resolution_rate", "—", help=info_tooltip("metrics.false_resolution_rate"))
    with c2:
        info_popover("metrics.false_resolution_rate")

    st.markdown("#### Gold-set metrics (precision / recall / F1)")
    st.caption(
        "Load a gold CSV (output/gold/gold_*.csv) to compute per-category precision, recall, F1 "
        "with worked examples."
    )
    up = st.file_uploader("Upload a gold CSV", type=["csv"], key="gold_uploader")
    if up is not None:
        import io

        gold_df = pd.read_csv(io.BytesIO(up.getvalue()))
        st.dataframe(gold_df.head(), use_container_width=True, hide_index=True)
        # Convert to the format the evaluator expects
        gold_records = gold_df.to_dict(orient="records")
        pred_records = [
            {
                "category": f.get("category"),
                "chunk_id": f.get("chunk_id"),
                "span_char_start": f.get("span_char_start", 0),
                "span_char_end": f.get("span_char_end", 0),
            }
            for f in flags
            if f.get("status") == "CONFIRMED"
        ]
        try:
            from src.evaluator import detection_metrics
            m = detection_metrics(pred_records, gold_records)
            st.dataframe(pd.DataFrame(m["per_category"]), use_container_width=True, hide_index=True)
            st.metric("F1 (macro)", f"{m['overall']['f1_macro']:.3f}", help=info_tooltip("metrics.f1"))
        except Exception as e:
            st.error(f"metric computation failed: {e}")


def _graph_tab():
    data = st.session_state.get("current_run_data")
    graph = (data or {}).get("graph") or {}
    render_graph_panel(graph)


def _pipeline_tab():
    st.markdown("### Pipeline history")
    runs = list_runs()
    if not runs:
        st.info("No runs yet.")
        return
    for r in runs[:30]:
        data = load_pipeline_result(r)
        res = data.get("result") or {}
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.5, 2, 2, 2])
            c1.markdown(f"**{r}**")
            c1.caption(", ".join(res.get("doc_ids", []))[:80])
            c2.metric("Chunks", res.get("n_chunks", 0))
            c3.metric("Confirmed", res.get("n_flags_confirmed", 0))
            c4.metric("Elapsed (s)", f"{res.get('elapsed_seconds', 0):.1f}")
            info_popover("stages.parse", label="ℹ pipeline stages")

    st.markdown("---")
    st.markdown("#### LLM call inspector")
    run_id = st.selectbox("Pick a run", runs, key="llm_inspect_run")
    llm_log = Path(config.OUTPUT_DIR) / run_id / "llm_calls.jsonl"
    if llm_log.exists():
        rows = []
        for ln in llm_log.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
        if rows:
            df = pd.DataFrame(
                [{
                    "call_id": r.get("call_id"),
                    "stage": r.get("stage"),
                    "model": r.get("model"),
                    "ms": r.get("elapsed_ms"),
                    "parse_ok": r.get("parse_ok"),
                    "error": r.get("error", "") or "",
                } for r in rows]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
            if rows:
                idx = st.number_input("Inspect call #", min_value=0, max_value=len(rows) - 1, value=0, step=1)
                call = rows[int(idx)]
                with st.expander("Prompt"):
                    st.code(call.get("prompt", "")[:6000], language="text")
                with st.expander("Raw response"):
                    st.code(call.get("response_raw", "")[:6000], language="text")
                with st.expander("Parsed response"):
                    st.json(call.get("response_parsed"))
    else:
        st.caption("No LLM call log for this run.")


def _experiments_tab():
    st.markdown("### Experiments (ablations)")
    st.caption(
        "Each ablation toggles one component and re-runs on the current run's data. "
        "Click (ℹ) for what/why/how/expected. "
        "Ablation runs are stored under `output/experiments/` — run them from the CLI (`python -m src.experiments --run-all`) "
        "for the full matrix."
    )
    abls = explain.get("ablations") or {}
    for k, v in abls.items():
        if not isinstance(v, dict):
            continue
        with st.container(border=True):
            c1, c2 = st.columns([6, 1])
            with c1:
                st.markdown(f"**{v.get('title', k)}**")
                if v.get("what"):
                    st.caption(v["what"])
                if v.get("expected"):
                    st.caption(f"Expected: {v['expected']}")
            with c2:
                info_popover(f"ablations.{k}")


def _about_tab():
    render_method_panel()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    _header()
    _sidebar()

    tabs = st.tabs(
        ["Analyse", "Annotate", "Metrics", "Graph Explorer", "Pipeline", "Experiments", "About this method"]
    )
    with tabs[0]:
        _analyse_tab()
    with tabs[1]:
        _annotate_tab()
    with tabs[2]:
        _metrics_tab()
    with tabs[3]:
        _graph_tab()
    with tabs[4]:
        _pipeline_tab()
    with tabs[5]:
        _experiments_tab()
    with tabs[6]:
        _about_tab()


if __name__ == "__main__":
    main()
