"""Tender Ambiguity Detector — Streamlit entry point (Prompt-4 package-aware)."""
from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
import zipfile
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
# Header + tour + glossary
# ---------------------------------------------------------------------------


def _onboarding_tour():
    steps = [
        ("Welcome", "TAD reads a whole Indian construction tender *package* and flags 8 kinds of ambiguity. Every number has an (ℹ) icon — click any of them to see what it means."),
        ("Upload your package", "Go to **Analyse**. Drop all PDFs for the tender (GCC, NIT, Specs, BOQ, Drawings, Addenda). Tag each document's type and pick which ones to analyse."),
        ("Dual-scoring detection", "Every chunk gets a **keyword score** (from the lexicon) and an **LLM score** (from a single calibrated call). Combined above the threshold → flagged."),
        ("Package context resolution", "For each flag, TAD retrieves context from the *whole* tender package. If a different document defines the term, the flag becomes **Resolved by Context** — not a real ambiguity."),
        ("Standards-grounded rewrite", "For **Confirmed Ambiguous** flags, TAD drafts a replacement clause grounded in IS codes and CPWD specifications."),
        ("About this method", "The About tab has the full method diagram, the eight categories, the verdicts, and the metrics."),
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
    with st.expander("📚 Glossary", expanded=True):
        all_expl = explain.all_explanations()
        groups = {
            "Categories": all_expl.get("categories", {}),
            "Verdicts": all_expl.get("verdicts", {}),
            "Scoring": all_expl.get("scoring", {}),
            "Metrics": all_expl.get("metrics", {}),
            "Stages": all_expl.get("stages", {}),
            "Document types": all_expl.get("document_types", {}),
            "Parameters": all_expl.get("params", {}),
        }
        for gname, items in groups.items():
            st.markdown(f"### {gname}")
            for k, v in items.items():
                if not isinstance(v, dict):
                    continue
                st.markdown(f"- **{v.get('title', k)}** — {v.get('what', '')}")


def _header():
    st.markdown(
        """
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:4px 0 8px 0;border-bottom:1px solid #E6E8EB;margin-bottom:10px'>
          <div>
            <div style='font-size:1.35rem;font-weight:700;color:#1F4E79'>📑 Tender Ambiguity Detector</div>
            <div style='color:#555;font-size:0.88rem'>Package upload · Dual-scoring detection · Two-stage RAG · Standards-grounded rewrite.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, _ = st.columns([1, 1, 8])
    with c1:
        if st.button("❓ What is this?", help="6-step tour of the app"):
            st.session_state["show_tour"] = True
    with c2:
        if st.button("📚 Glossary"):
            st.session_state["show_glossary"] = not st.session_state.get("show_glossary", False)
    if st.session_state.get("show_tour"):
        _onboarding_tour()
    if st.session_state.get("show_glossary"):
        _glossary_modal()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _sidebar():
    with st.sidebar:
        st.markdown("### Run configuration")

        st.markdown("**Enabled categories**")
        st.caption("Pick which ambiguity categories the detector will run.")
        cats_enabled = []
        for cat in config.ENABLED_CATEGORIES:
            name = explain.category_display(cat)
            c1, c2 = st.columns([5, 1])
            with c1:
                on = st.checkbox(name, value=True, key=f"en_{cat}", help=info_tooltip(f"categories.{cat}"))
            with c2:
                info_popover(f"categories.{cat}", label="ℹ")
            if on:
                cats_enabled.append(cat)
        st.session_state["enabled_categories"] = cats_enabled

        st.markdown("---")
        st.markdown("**Scoring**")
        c1, c2 = st.columns([5, 1])
        with c1:
            alpha = st.slider(
                "Keyword weight α",
                0.0,
                1.0,
                value=float(config.KEYWORD_SCORE_WEIGHT_ALPHA),
                step=0.05,
                help=info_tooltip("scoring.alpha"),
            )
        with c2:
            info_popover("scoring.alpha")
        st.session_state["alpha"] = alpha

        c1, c2 = st.columns([5, 1])
        with c1:
            thr = st.slider(
                "Detection threshold",
                0.0,
                1.0,
                value=float(config.DETECTION_THRESHOLD),
                step=0.05,
                help=info_tooltip("scoring.detection_threshold"),
            )
        with c2:
            info_popover("scoring.detection_threshold")
        st.session_state["threshold"] = thr

        st.markdown("---")
        st.markdown("**Guardrails**")
        for key, label, expl_key in [
            ("disable_neg_probe", "G2 — negative-control probe", "stages.detect"),
            ("disable_citation_judge", "G3 — citation judge", "stages.judge_citations"),
            ("disable_ground_verify", "G4 — grounding verification", "stages.verify_grounding"),
        ]:
            c1, c2 = st.columns([5, 1])
            with c1:
                on = st.checkbox(label, value=True, help=info_tooltip(expl_key))
                st.session_state[key] = not on
            with c2:
                info_popover(expl_key, label="ℹ")

        st.markdown("---")
        c1, c2 = st.columns([5, 1])
        with c1:
            use_legacy = st.checkbox(
                "Use legacy 3-pass ensemble",
                value=bool(config.USE_LEGACY_ENSEMBLE),
                help=info_tooltip("params.USE_LEGACY_ENSEMBLE"),
            )
        with c2:
            info_popover("params.USE_LEGACY_ENSEMBLE", label="ℹ")
        st.session_state["use_legacy_ensemble"] = use_legacy

        st.markdown("---")
        st.markdown("**Models in use**")
        with st.expander("Show"):
            for k, v in config.dump().items():
                st.markdown(f"- `{k}` = `{v}`")

        st.caption("TAD — M.Tech thesis project, IIT Bombay.")


# ---------------------------------------------------------------------------
# Analyse tab — package flow
# ---------------------------------------------------------------------------


def _stage_pdfs(uploaded_files, zip_bytes, staging: Path) -> list[Path]:
    """Write UploadedFile objects / ZIP contents to the staging dir and return paths."""
    staging.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for u in uploaded_files or []:
        p = staging / u.name
        p.write_bytes(u.getvalue() if hasattr(u, "getvalue") else u.read())
        out.append(p)
    if zip_bytes:
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
            for name in zf.namelist():
                if not name.lower().endswith(".pdf"):
                    continue
                base = Path(name).name
                if not base:
                    continue
                p = staging / base
                p.write_bytes(zf.read(name))
                out.append(p)
        except Exception as e:
            st.error(f"Could not read zip: {e}")
    return out


def _auto_type_hint(filename: str) -> str:
    from src.pipeline import _auto_document_type
    return _auto_document_type(filename)


def _analyse_tab():
    st.markdown("### Analyse a tender package")
    st.caption(
        "Upload all PDFs belonging to a single tender (GCC, NIT, Specs, BOQ, Drawings, Addenda). "
        "Tag each document and pick which ones to analyse. Every (ℹ) opens a full explanation."
    )

    sample_dir = Path(__file__).resolve().parent.parent / "data" / "sample_tenders"
    samples = sorted(sample_dir.glob("*.pdf")) if sample_dir.exists() else []

    # Upload
    c1, c2 = st.columns([3, 2])
    with c1:
        pdfs_upload = st.file_uploader(
            "Upload PDFs (multiple)", type=["pdf"], accept_multiple_files=True, key="pkg_pdfs"
        )
    with c2:
        zip_upload = st.file_uploader(
            "…or upload a single ZIP containing the PDFs",
            type=["zip"],
            accept_multiple_files=False,
            key="pkg_zip",
        )

    # Sample shortcut
    sample_name = st.selectbox(
        "…or pick a sample tender (appended)",
        options=["— none —"] + [p.name for p in samples],
        help=info_tooltip("document_types.Other"),
    )

    # Materialise files into a staging dir
    staging = Path(__file__).resolve().parent.parent / "output" / "_uploads" / f"session_{st.session_state.get('session_id') or 'default'}"
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = uuid.uuid4().hex[:8]
        staging = Path(__file__).resolve().parent.parent / "output" / "_uploads" / f"session_{st.session_state['session_id']}"
    staging.mkdir(parents=True, exist_ok=True)

    pdf_paths: list[Path] = []
    if pdfs_upload or zip_upload:
        pdf_paths = _stage_pdfs(
            pdfs_upload or [],
            zip_upload.getvalue() if zip_upload else None,
            staging,
        )
    if sample_name and sample_name != "— none —":
        pdf_paths.append(sample_dir / sample_name)

    # Document typing + selection table
    doc_types: dict[str, str] = {}
    analyse_flags: dict[str, bool] = {}
    analyse_selection: dict[str, tuple[int, int] | None] = {}

    if pdf_paths:
        st.markdown("#### Package contents")
        h1, h2, h3, h4, h5, h6 = st.columns([3, 3, 1, 1, 1.5, 0.5])
        h1.markdown("**Filename**")
        h2.markdown("**Document type**")
        h3.markdown("**Size**")
        h4.markdown("**Analyse**")
        h5.markdown("**Page range**")
        with h6:
            info_popover("document_types.GCC", label="ℹ")
        for p in pdf_paths:
            c1, c2, c3, c4, c5, c6 = st.columns([3, 3, 1, 1, 1.5, 0.5])
            with c1:
                st.markdown(f"`{p.name}`")
            with c2:
                idx = config.PACKAGE_DOCUMENT_TYPES.index(
                    _auto_type_hint(p.name)
                ) if _auto_type_hint(p.name) in config.PACKAGE_DOCUMENT_TYPES else 0
                sel = st.selectbox(
                    f"type_{p.name}",
                    options=config.PACKAGE_DOCUMENT_TYPES,
                    index=idx,
                    key=f"dt_{p.name}",
                    label_visibility="collapsed",
                )
                doc_types[p.name] = sel
            with c3:
                try:
                    st.caption(f"{p.stat().st_size // 1024} KB")
                except Exception:
                    st.caption("?")
            with c4:
                analyse_flags[p.name] = st.checkbox(
                    f"an_{p.name}", value=True, key=f"an_{p.name}", label_visibility="collapsed"
                )
            with c5:
                rng = st.text_input(
                    f"pg_{p.name}",
                    value="",
                    placeholder="e.g. 3-12",
                    key=f"pg_{p.name}",
                    label_visibility="collapsed",
                )
                if rng.strip():
                    try:
                        s, e = rng.split("-")
                        analyse_selection[p.name] = (int(s), int(e))
                    except Exception:
                        analyse_selection[p.name] = None
                else:
                    analyse_selection[p.name] = None
            with c6:
                info_popover(f"document_types.{doc_types[p.name]}", label="ℹ")

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric(
                "Documents uploaded",
                len(pdf_paths),
                help="Total PDFs in this tender package (all indexed for retrieval).",
            )
        with m2:
            st.metric(
                "Documents selected for flag generation",
                sum(1 for k, v in analyse_flags.items() if v),
                help="Flags are generated only from these documents; the others still contribute to Stage 2 retrieval.",
            )
        with m3:
            st.metric(
                "Document types present",
                len({t for t in doc_types.values()}),
                help="Distinct tag types across the uploaded files.",
            )

    # Run button
    cc1, cc2 = st.columns([1, 5])
    with cc1:
        run_btn = st.button("▶ Run pipeline", type="primary", use_container_width=True, disabled=not pdf_paths)
    with cc2:
        st.caption("Runs parse → chunk → index package → dual-scoring detection → package context resolution → standards-grounded rewrite.")

    tracker_placeholder = st.container()
    progress_placeholder = st.empty()

    if run_btn and pdf_paths:
        progress = {}

        def _cb(stage, pct, msg):
            progress[stage] = max(pct, progress.get(stage, 0.0))
            with tracker_placeholder:
                render_tracker(progress, active_stage=stage)
            progress_placeholder.info(f"{stage}: {msg}")

        try:
            result = run_pipeline(
                pdf_paths,
                package_types=doc_types,
                analyse_selection=analyse_selection,
                analyse_flags=analyse_flags,
                enabled_categories=st.session_state.get("enabled_categories"),
                alpha=st.session_state.get("alpha"),
                threshold=st.session_state.get("threshold"),
                disable_neg_probe=st.session_state.get("disable_neg_probe", False),
                disable_citation_judge=st.session_state.get("disable_citation_judge", False),
                disable_ground_verify=st.session_state.get("disable_ground_verify", False),
                use_legacy_ensemble=st.session_state.get("use_legacy_ensemble", False),
                progress_cb=_cb,
            )
            progress_placeholder.success(
                f"Pipeline complete in {result.elapsed_seconds:.1f}s — run_id = {result.run_id}"
            )
            st.session_state["last_run_id"] = result.run_id
        except Exception as e:
            progress_placeholder.error(f"Pipeline failed: {e}")
            st.exception(e)

    # --- Results browsing ---
    st.markdown("---")
    runs = list_runs()
    if not runs:
        st.info("No completed runs yet. Upload a tender package and run the pipeline above.")
        return
    default_run = st.session_state.get("last_run_id") or runs[0]
    if default_run not in runs:
        default_run = runs[0]
    run_id = st.selectbox("Pick a run to view", runs, index=runs.index(default_run))
    data = load_pipeline_result(run_id)
    st.session_state["current_run_data"] = data

    result = data.get("result", {}) or {}
    legacy_badge = " · legacy ensemble" if data.get("is_legacy_run") else ""
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Chunks", result.get("n_chunks", 0), help=info_tooltip("stages.chunk"))
    m2.metric("Confirmed Stage-1 flags" + legacy_badge, result.get("n_flags_confirmed", 0), help=info_tooltip("stages.detect"))
    m3.metric("Review queue", result.get("n_flags_review", 0), help=info_tooltip("stages.detect"))
    m4.metric("Stage-2 verdicts", result.get("n_resolutions", 0), help=info_tooltip("stages.resolve"))
    m5.metric("Stage-3 rewrites", result.get("n_rewrites", 0), help=info_tooltip("stages.rewrite"))

    flags = data.get("flags") or []
    chunks_list = data.get("chunks") or []
    chunks_map = {c.get("id"): c for c in chunks_list}
    resolutions_map = {r.get("flag_id"): r for r in (data.get("resolutions") or [])}
    rewrites_map = {r.get("flag_id"): r for r in (data.get("rewrites") or [])}

    def _verdict_for(flag):
        r = resolutions_map.get(flag.get("id"))
        return r.get("verdict") if r else None

    # Filter bar
    filt_cols = st.columns([2.2, 2.2, 2, 2])
    with filt_cols[0]:
        cat_display_opts = sorted(
            {f.get("category") for f in flags if f.get("category")},
            key=lambda x: explain.category_display(x),
        )
        sel_cats = st.multiselect(
            "Categories",
            options=cat_display_opts,
            format_func=explain.category_display,
        )
    with filt_cols[1]:
        verdict_opts = ["CONFIRMED_AMBIGUOUS", "PARTIALLY_RESOLVED", "RESOLVED_BY_CONTEXT", "(no verdict)"]
        sel_verdicts = st.multiselect(
            "Verdict",
            options=verdict_opts,
            format_func=lambda v: explain.verdict_display(v) if v != "(no verdict)" else "(no verdict)",
        )
    with filt_cols[2]:
        doc_types_in_run = sorted({c.get("document_type") for c in chunks_list if c.get("document_type")})
        sel_docs = st.multiselect("Document type", options=doc_types_in_run)
    with filt_cols[3]:
        sort_by = st.selectbox("Sort by", ["combined_score", "llm_score", "keyword_score", "category"], index=0)

    def _pred(f):
        if sel_cats and f.get("category") not in sel_cats:
            return False
        v = _verdict_for(f) or "(no verdict)"
        # Normalise legacy synonyms
        v_norm = {"RESOLVED": "RESOLVED_BY_CONTEXT", "UNRESOLVED": "CONFIRMED_AMBIGUOUS"}.get(v, v)
        if sel_verdicts and v_norm not in sel_verdicts:
            return False
        chk = chunks_map.get(f.get("chunk_id")) or {}
        if sel_docs and chk.get("document_type") not in sel_docs:
            return False
        return True

    selected_flags = [f for f in flags if _pred(f)]
    if sort_by == "category":
        selected_flags.sort(key=lambda x: explain.category_display(x.get("category", "")))
    else:
        selected_flags.sort(key=lambda x: float(x.get(sort_by) or 0), reverse=True)

    # Split into Confirmed vs Resolved buckets
    def _bucket(f):
        v = _verdict_for(f)
        if explain.verdict_display(v or "") == "Resolved by Context":
            return "resolved"
        return "confirmed"

    confirmed = [f for f in selected_flags if _bucket(f) == "confirmed"]
    resolved = [f for f in selected_flags if _bucket(f) == "resolved"]

    st.caption(f"Showing {len(selected_flags)} of {len(flags)} flags · {len(confirmed)} Confirmed / {len(resolved)} Resolved by Context")

    def _render_cards(fs):
        for f in fs[:200]:
            chk = chunks_map.get(f.get("chunk_id")) or {}
            render_flag_card(
                f,
                chk.get("text", "") or "",
                chk,
                resolutions_map.get(f.get("id")),
                rewrites_map.get(f.get("id")),
            )

    st.markdown("## ⚠ Confirmed Ambiguous flags")
    if not confirmed:
        st.caption("No confirmed flags in this run (or all filtered out).")
    _render_cards(confirmed)

    if resolved:
        st.markdown("## ✅ Resolved by Context — context found elsewhere in the package")
        st.caption(
            "These flags looked ambiguous in the flagged chunk but were disambiguated by other documents in the package. "
            "Shown here for transparency — no rewrite is needed."
        )
        _render_cards(resolved)

    # Exports
    st.markdown("---")
    if flags:
        df = pd.DataFrame(flags)
        df["category_name"] = df["category"].apply(explain.category_display)
        st.download_button(
            "⬇ Download flags CSV (with display names)",
            df.to_csv(index=False),
            file_name=f"flags_{run_id}.csv",
        )


# ---------------------------------------------------------------------------
# Annotate tab
# ---------------------------------------------------------------------------


def _annotate_tab():
    st.markdown("### Annotate (gold-set spot-check)")
    st.caption("Confirm or reject each flag. Your verdicts override the automated judge.")
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
                    f"**{explain.category_display(f.get('category'))}** — `{(f.get('span_text') or '')[:80]}`  "
                    f"(combined={float(f.get('combined_score', 0)):.2f}, kw={float(f.get('keyword_score', 0)):.2f}, "
                    f"llm={float(f.get('llm_score', 0)):.2f})"
                )
                chk = chunks_map.get(f.get("chunk_id"))
                if chk:
                    st.caption((chk.get("text") or "")[:260])
            with c2:
                options = ["(not decided)", "TRUE_POSITIVE", "FALSE_POSITIVE", "WRONG_CATEGORY", "UNCERTAIN"]
                cur = gold.get(f.get("id"), {}).get("decision", "(not decided)")
                idx = options.index(cur) if cur in options else 0
                dec = st.selectbox(
                    f"Label flag {i+1}", options, index=idx, key=f"ann_{f.get('id')}", label_visibility="collapsed"
                )
                if dec != "(not decided)":
                    gold[f.get("id")] = {"decision": dec, "flag": f}
            with c3:
                info_popover(f"categories.{f.get('category')}", label="ℹ category definition")

    if gold:
        df = pd.DataFrame(
            {
                "flag_id": k,
                "category": v["flag"].get("category"),
                "category_name": explain.category_display(v["flag"].get("category")),
                "span_text": v["flag"].get("span_text"),
                "decision": v["decision"],
            }
            for k, v in gold.items()
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇ Download gold CSV", df.to_csv(index=False), file_name="gold_annotations.csv")


# ---------------------------------------------------------------------------
# Metrics tab
# ---------------------------------------------------------------------------


def _metrics_tab():
    st.markdown("### Metrics")
    st.caption("Every metric has an (ℹ) popover with worked examples.")

    data = st.session_state.get("current_run_data")
    if not data:
        st.info("Run the pipeline first on the Analyse tab.")
        return

    flags = data.get("flags") or []
    resolutions = data.get("resolutions") or []
    alpha = st.session_state.get("alpha", config.KEYWORD_SCORE_WEIGHT_ALPHA)

    # Flag distribution
    per_cat: dict[str, int] = {}
    for f in flags:
        if f.get("status") != "CONFIRMED":
            continue
        per_cat[f.get("category")] = per_cat.get(f.get("category"), 0) + 1
    if per_cat:
        df = pd.DataFrame(
            {"category": [explain.category_display(k) for k in per_cat.keys()], "count": list(per_cat.values())}
        ).sort_values("category")
        st.markdown("#### Flag distribution (confirmed at Stage 1)")
        st.bar_chart(df.set_index("category"))

    # Verdict distribution (Stage 2)
    st.markdown("#### Stage 2 verdict distribution")
    counts = {"CONFIRMED_AMBIGUOUS": 0, "PARTIALLY_RESOLVED": 0, "RESOLVED_BY_CONTEXT": 0}
    for r in resolutions:
        v = r.get("verdict") or ""
        v = {"RESOLVED": "RESOLVED_BY_CONTEXT", "UNRESOLVED": "CONFIRMED_AMBIGUOUS"}.get(v, v)
        if v in counts:
            counts[v] += 1
    cols = st.columns(3)
    for i, (k, n) in enumerate(counts.items()):
        with cols[i]:
            st.metric(explain.verdict_display(k), n, help=info_tooltip(f"verdicts.{k}"))
            info_popover(f"verdicts.{k}")

    # Resolved-by-context rate
    total_confirmed = sum(1 for f in flags if f.get("status") == "CONFIRMED")
    rbc_rate = counts["RESOLVED_BY_CONTEXT"] / total_confirmed if total_confirmed else 0.0
    c1, c2 = st.columns([5, 1])
    with c1:
        st.metric(
            "Resolved-by-context rate",
            f"{rbc_rate * 100:.1f}%",
            help=info_tooltip("metrics.resolved_by_context_rate"),
        )
    with c2:
        info_popover("metrics.resolved_by_context_rate")

    # Keyword vs LLM contribution
    st.markdown("#### Keyword vs LLM contribution (per category)")
    contrib_rows = []
    for cat in sorted({f.get("category") for f in flags if f.get("status") == "CONFIRMED"}):
        subset = [f for f in flags if f.get("category") == cat and f.get("status") == "CONFIRMED"]
        kw_led = sum(
            1
            for f in subset
            if alpha * float(f.get("keyword_score", 0)) > (1 - alpha) * float(f.get("llm_score", 0))
        )
        llm_led = len(subset) - kw_led
        contrib_rows.append({
            "category": explain.category_display(cat),
            "keyword-led": kw_led,
            "llm-led": llm_led,
        })
    if contrib_rows:
        st.dataframe(pd.DataFrame(contrib_rows), use_container_width=True, hide_index=True)
    info_popover("metrics.keyword_vs_llm_contribution", label="ℹ what does keyword-led mean?")

    # Safety metric
    st.markdown("#### Safety metric — false-resolution rate")
    c1, c2 = st.columns([5, 1])
    with c1:
        st.metric("false_resolution_rate", "—", help=info_tooltip("metrics.false_resolution_rate"))
    with c2:
        info_popover("metrics.false_resolution_rate")
    st.caption("Populated when you upload an audit CSV of spot-checked RESOLVED_BY_CONTEXT verdicts.")


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
        legacy = data.get("is_legacy_run")
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.5, 2, 2, 2])
            c1.markdown(f"**{r}**")
            if legacy:
                c1.markdown(
                    "<span style='background:#888;color:white;padding:2px 6px;border-radius:6px;font-size:0.72rem'>Legacy ensemble run</span>",
                    unsafe_allow_html=True,
                )
            c1.caption(", ".join(res.get("doc_ids", []))[:80])
            c2.metric("Chunks", res.get("n_chunks", 0))
            c3.metric("Confirmed", res.get("n_flags_confirmed", 0))
            c4.metric("Elapsed (s)", f"{res.get('elapsed_seconds', 0):.1f}")
            info_popover("stages.detect", label="ℹ pipeline stages")

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
                    "error": r.get("error") or "",
                } for r in rows]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
            if rows:
                idx = st.number_input("Inspect call #", min_value=0, max_value=len(rows) - 1, value=0, step=1)
                call = rows[int(idx)]
                with st.expander("Prompt"):
                    st.code((call.get("prompt") or "")[:6000], language="text")
                with st.expander("Raw response"):
                    st.code((call.get("response_raw") or "")[:6000], language="text")
                with st.expander("Parsed response"):
                    st.json(call.get("response_parsed"))
    else:
        st.caption("No LLM call log for this run.")


def _experiments_tab():
    st.markdown("### Experiments (ablations)")
    st.caption("Each ablation toggles one component. Run the full suite via `python -m src.experiments --run-all`.")
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
