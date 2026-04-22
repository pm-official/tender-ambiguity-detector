"""End-to-end pipeline — Prompt-4 package-oriented.

Flow:
  ingest_package(paths, types, selection) -> TenderPackage
  run_pipeline(package, ...) -> PipelineResult
  Stages: Parse -> Chunk -> Index (whole package) -> Dual-Score -> Package Context -> Standards Rewrite
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd

from . import config, explain
from .chunker import chunk_pages
from .detector import detect_dual, detect_legacy_ensemble
from .embeddings import VectorStore
from .graph_builder import build_graph
from .parser import ParsedPage, parse_many
from .resolver import resolve
from .rewriter import rewrite
from .schemas import (
    Chunk,
    DualScoredFlag,
    PackageDocument,
    PipelineResult,
    Resolution,
    Rewrite,
    TenderPackage,
)
from .utils import active_run_dir, logger, new_run_id, set_active_run


# ---------------------------------------------------------------------------
# Package ingestion
# ---------------------------------------------------------------------------


def _auto_document_type(filename: str) -> str:
    fn = filename.lower()
    if "gcc" in fn or "general_conditions" in fn or "general-conditions" in fn:
        return "GCC"
    if "nit" in fn or "notice" in fn or "invit" in fn:
        return "NIT"
    if "boq" in fn or "bill-of-quantities" in fn or "bill_of_quantities" in fn or "schedule" in fn:
        return "BOQ"
    if "addendum" in fn or "addenda" in fn or "corrigend" in fn:
        return "Addendum"
    if "drawing" in fn or fn.endswith("_dwg.pdf") or "-dwg" in fn:
        return "Drawing"
    if "spec" in fn:
        return "Technical Specifications"
    if "particular" in fn or "additional" in fn:
        return "Additional Conditions"
    if "conditions" in fn:
        return "Conditions of Contract"
    return "Other"


def ingest_package(
    paths: list[Path],
    *,
    types: dict[str, str] | None = None,
    analyse_selection: dict[str, tuple[int, int] | None] | None = None,
    analyse_flags: dict[str, bool] | None = None,
    package_id: str | None = None,
) -> TenderPackage:
    """Parse, chunk, embed, and build the TenderPackage manifest.

    types:  filename -> document_type (defaults to _auto_document_type).
    analyse_selection: filename -> (page_start, page_end) or None (full doc).
    analyse_flags:    filename -> bool (default True).
    """
    package_id = package_id or f"pkg_{uuid.uuid4().hex[:10]}"
    types = types or {}
    analyse_flags = analyse_flags or {}
    analyse_selection = analyse_selection or {}

    documents: list[PackageDocument] = []
    all_pages: list[ParsedPage] = []
    for pth in paths:
        pages = parse_many([pth])
        all_pages.extend(pages)
        fn = pth.name
        doc_id = pages[0].doc_id if pages else pth.stem
        doc_type = types.get(fn) or _auto_document_type(fn)
        documents.append(
            PackageDocument(
                doc_id=doc_id,
                filename=fn,
                document_type=doc_type,  # type: ignore[arg-type]
                num_pages=len({p.page for p in pages}),
                analyse=analyse_flags.get(fn, True),
                page_range=analyse_selection.get(fn),
            )
        )

    # Chunk every parsed page; annotate chunks with package_id + document_type
    doc_type_by_id = {d.doc_id: d.document_type for d in documents}
    chunks = chunk_pages(all_pages, max_tokens=config.CHUNK_MAX_TOKENS, overlap_tokens=config.CHUNK_OVERLAP)
    for c in chunks:
        c.package_id = package_id
        c.document_type = doc_type_by_id.get(c.doc_id)

    # Embed into the package collection
    vs = VectorStore()
    vs.reset_package(package_id=package_id)
    vs.add_chunks(chunks, collection="package")

    # Stash chunks for run time
    active_run_dir().joinpath("_ingest_chunks.json").write_text(
        json.dumps([c.model_dump() for c in chunks], indent=2), encoding="utf-8"
    )
    return TenderPackage(package_id=package_id, documents=documents)


def _load_ingest_chunks() -> list[Chunk]:
    p = active_run_dir() / "_ingest_chunks.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [Chunk.model_validate(r) for r in raw]


def _filter_candidate_chunks(chunks: list[Chunk], package: TenderPackage) -> list[Chunk]:
    """Only chunks from user-selected documents (respecting page ranges) can produce flags."""
    by_doc = {d.doc_id: d for d in package.documents}
    out: list[Chunk] = []
    for c in chunks:
        d = by_doc.get(c.doc_id)
        if d is None or not d.analyse:
            continue
        if d.page_range:
            ps, pe = d.page_range
            if c.page < ps or c.page > pe:
                continue
        out.append(c)
    return out


# ---------------------------------------------------------------------------
# Pipeline run
# ---------------------------------------------------------------------------


def run_pipeline(
    pdfs_or_package,
    *,
    run_id: str | None = None,
    enabled_categories: list[str] | None = None,
    alpha: float | None = None,
    threshold: float | None = None,
    disable_neg_probe: bool = False,
    disable_citation_judge: bool = False,
    disable_ground_verify: bool = False,
    use_legacy_ensemble: bool | None = None,
    package_types: dict[str, str] | None = None,
    analyse_selection: dict[str, tuple[int, int] | None] | None = None,
    analyse_flags: dict[str, bool] | None = None,
    progress_cb=None,
) -> PipelineResult:
    """Run the full pipeline on either a list of PDFs (packaged implicitly) or a TenderPackage."""

    run_id = run_id or new_run_id()
    rd = set_active_run(run_id)
    t0 = time.time()

    def tick(stage: str, pct: float = 0.0, msg: str = ""):
        if progress_cb:
            progress_cb(stage, pct, msg)

    # 1) Coerce input into a TenderPackage
    tick("parse", 0.02, "Parsing tender package")
    if isinstance(pdfs_or_package, TenderPackage):
        package = pdfs_or_package
        chunks = _load_ingest_chunks()
    else:
        paths = [Path(p) for p in (pdfs_or_package if isinstance(pdfs_or_package, list) else [pdfs_or_package])]
        package = ingest_package(
            paths,
            types=package_types,
            analyse_selection=analyse_selection,
            analyse_flags=analyse_flags,
        )
        chunks = _load_ingest_chunks()

    # Save package manifest
    (rd / "package_manifest.json").write_text(
        json.dumps(package.model_dump(), indent=2), encoding="utf-8"
    )
    pd.DataFrame([c.model_dump() for c in chunks]).to_csv(rd / "chunks.csv", index=False)
    tick("chunk", 0.15, f"{len(chunks)} chunks indexed")
    tick("embed", 0.25, f"Package embedded ({len(package.documents)} documents)")

    # 2) Candidate chunks (selected docs only produce flags)
    candidates = _filter_candidate_chunks(chunks, package)
    if not candidates:
        logger.warning("no candidate chunks to analyse — check document selection / page ranges")
        candidates = chunks  # fall back to analysing the whole package

    # 3) Build the graph (only over candidates — graph-routed categories need cross-doc)
    tick("graph", 0.35, "Building tender knowledge graph")
    graph = build_graph(candidates)
    graph.find_numeric_conflicts()
    graph.save_json(rd / "graph.json")

    # 4) Detection — dual scoring (or legacy ensemble if the ablation flag is on)
    vs = VectorStore()
    use_legacy = use_legacy_ensemble if use_legacy_ensemble is not None else config.USE_LEGACY_ENSEMBLE

    tick("detect", 0.45, "Dual-scoring detection" if not use_legacy else "Legacy 3-pass ensemble")

    def _det_cb(step, total, msg):
        if progress_cb:
            pct = 0.45 + 0.25 * (step / max(1, total))
            progress_cb("detect", pct, msg)

    if use_legacy:
        legacy_flags = detect_legacy_ensemble(
            candidates,
            enabled_categories=enabled_categories,
            disable_neg_probe=disable_neg_probe,
            progress_cb=_det_cb,
        )
        flags: list[DualScoredFlag] = [
            DualScoredFlag(
                id=c.id,
                chunk_id=c.chunk_id,
                category=c.category,
                span_text=c.span_text,
                span_char_start=c.span_char_start,
                span_char_end=c.span_char_end,
                keyword_score=0.0,
                llm_score=c.mean_confidence,
                combined_score=c.mean_confidence,
                justification="; ".join(p.justification for p in c.passes)[:400],
                package_id=package.package_id,
                status=c.status,
            )
            for c in legacy_flags
        ]
    else:
        flags = detect_dual(
            candidates,
            enabled_categories=enabled_categories,
            alpha=alpha,
            threshold=threshold,
            disable_neg_probe=disable_neg_probe,
            package_id=package.package_id,
            progress_cb=_det_cb,
        )

    pd.DataFrame([f.model_dump() for f in flags]).to_csv(rd / "flags.csv", index=False)

    # 5) Stage 2 — package context resolution (+ G3 citation judge)
    tick("resolve", 0.75, f"Resolving {sum(1 for f in flags if f.status == 'CONFIRMED')} confirmed flags")
    chunk_text_by_id = {c.id: c.text for c in chunks}
    resolutions: list[Resolution] = []
    confirmed = [f for f in flags if f.status == "CONFIRMED"]
    for i, f in enumerate(confirmed):
        if progress_cb:
            progress_cb("resolve", 0.75 + 0.10 * (i / max(1, len(confirmed))), f"Resolving {f.id}")
        res = resolve(
            f,
            chunk_text_by_id.get(f.chunk_id, ""),
            vector_store=vs,
            graph=graph,
            disable_citation_judge=disable_citation_judge,
        )
        resolutions.append(res)

    pd.DataFrame([r.model_dump() for r in resolutions]).to_csv(rd / "resolutions.csv", index=False)

    # 6) Stage 3 — standards-grounded rewrite (only on Confirmed / Partial)
    tick("rewrite", 0.88, "Writing standards-grounded rewrites")
    rewrites: list[Rewrite] = []
    flag_by_id = {f.id: f for f in flags}
    for res in resolutions:
        if res.verdict in ("RESOLVED_BY_CONTEXT", "RESOLVED"):
            continue
        flag = flag_by_id.get(res.flag_id)
        if flag is None:
            continue
        query = f"{explain.category_display(flag.category)}: {flag.span_text}"
        stds_ctx = vs.query_standards(query, top_k=config.TOP_K_ISCODE) if vs else []
        rw = rewrite(
            flag,
            chunk_text_by_id.get(flag.chunk_id, ""),
            res,
            standards_contexts=stds_ctx,
            disable_ground_verify=disable_ground_verify,
        )
        if rw is not None:
            rewrites.append(rw)

    pd.DataFrame([r.model_dump() for r in rewrites]).to_csv(rd / "rewrites.csv", index=False)

    tick("done", 1.0, "Pipeline complete")
    per_cat = {c: sum(1 for f in flags if f.category == c and f.status == "CONFIRMED") for c in config.ENABLED_CATEGORIES}

    result = PipelineResult(
        run_id=run_id,
        doc_ids=[d.doc_id for d in package.documents],
        n_chunks=len(chunks),
        n_flags_confirmed=sum(1 for f in flags if f.status == "CONFIRMED"),
        n_flags_review=sum(1 for f in flags if f.status == "REVIEW_QUEUE"),
        n_resolutions=len(resolutions),
        n_rewrites=len(rewrites),
        elapsed_seconds=time.time() - t0,
        per_category_counts=per_cat,
        artifact_paths={
            "package_manifest": str(rd / "package_manifest.json"),
            "chunks": str(rd / "chunks.csv"),
            "flags": str(rd / "flags.csv"),
            "resolutions": str(rd / "resolutions.csv"),
            "rewrites": str(rd / "rewrites.csv"),
            "graph": str(rd / "graph.json"),
            "llm_calls": str(rd / "llm_calls.jsonl"),
            "dual_scores": str(rd / "dual_scores.jsonl"),
        },
    )
    (rd / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def load_pipeline_result(run_id: str) -> dict:
    rd = Path(config.OUTPUT_DIR) / run_id
    out: dict = {}
    for name in ["result.json", "package_manifest.json", "graph.json"]:
        p = rd / name
        if p.exists():
            try:
                out[name.split(".")[0]] = json.loads(p.read_text())
            except Exception:
                pass
    for name in ["chunks.csv", "flags.csv", "resolutions.csv", "rewrites.csv"]:
        p = rd / name
        if p.exists():
            out[name.replace(".csv", "")] = pd.read_csv(p).to_dict(orient="records")
    # Legacy-run heuristic: missing keyword_score column → legacy ensemble run
    flags_list = out.get("flags") or []
    is_legacy = bool(flags_list) and not any("keyword_score" in row and row.get("keyword_score") not in (None, "") for row in flags_list)
    out["is_legacy_run"] = is_legacy
    return out


def list_runs() -> list[str]:
    d = Path(config.OUTPUT_DIR)
    if not d.exists():
        return []
    return sorted([p.name for p in d.iterdir() if p.is_dir() and (p / "result.json").exists()], reverse=True)
