"""End-to-end pipeline: parse → chunk → embed → graph → detect → resolve → rewrite."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable

import pandas as pd

from . import config
from .chunker import chunk_pages
from .detector import detect
from .embeddings import VectorStore
from .graph_builder import build_graph
from .graph_store import GraphStore
from .parser import parse_many
from .resolver import resolve
from .rewriter import rewrite
from .schemas import FlagCluster, PipelineResult, Resolution, Rewrite
from .utils import active_run_dir, logger, new_run_id, set_active_run


def run_pipeline(
    pdf_paths: list[Path] | Path,
    *,
    run_id: str | None = None,
    enabled_categories: list[str] | None = None,
    disable_neg_probe: bool = False,
    disable_citation_judge: bool = False,
    disable_ground_verify: bool = False,
    single_pass: bool = False,
    progress_cb=None,
) -> PipelineResult:
    if isinstance(pdf_paths, (str, Path)):
        pdf_paths = [Path(pdf_paths)]
    pdf_paths = [Path(p) for p in pdf_paths]

    run_id = run_id or new_run_id()
    rd = set_active_run(run_id)

    t0 = time.time()

    def tick(stage: str, pct: float = 0.0, msg: str = ""):
        if progress_cb:
            progress_cb(stage, pct, msg)

    tick("parse", 0.02, f"Parsing {len(pdf_paths)} PDF(s)")
    pages = parse_many(pdf_paths)
    (rd / "parse_report.json").write_text(
        json.dumps({"n_pages": len(pages), "docs": sorted({p.doc_id for p in pages})}, indent=2),
        encoding="utf-8",
    )
    tick("chunk", 0.10, "Chunking clauses")
    chunks = chunk_pages(pages, max_tokens=config.CHUNK_MAX_TOKENS, overlap_tokens=config.CHUNK_OVERLAP)
    pd.DataFrame([c.model_dump() for c in chunks]).to_csv(rd / "chunks.csv", index=False)

    tick("embed", 0.20, f"Embedding {len(chunks)} chunks")
    vs = VectorStore()
    vs.reset_tender()
    vs.add_chunks(chunks, collection="tender")

    tick("graph", 0.30, "Building knowledge graph")
    graph = build_graph(chunks)
    graph.find_numeric_conflicts()
    graph.save_json(rd / "graph.json")

    tick("detect", 0.40, "Running 3-pass ensemble detection")

    def _det_cb(step, total, msg):
        if progress_cb:
            pct = 0.40 + 0.30 * (step / max(1, total))
            progress_cb("detect", pct, msg)

    flags = detect(
        chunks,
        enabled_categories=enabled_categories,
        disable_neg_probe=disable_neg_probe,
        progress_cb=_det_cb,
    )
    pd.DataFrame([f.model_dump() for f in flags]).to_csv(rd / "flags.csv", index=False)

    tick("resolve", 0.75, f"Resolving {sum(1 for f in flags if f.status == 'CONFIRMED')} confirmed flags")
    chunk_text_by_id = {c.id: c.text for c in chunks}
    resolutions: list[Resolution] = []
    rewrites: list[Rewrite] = []
    confirmed = [f for f in flags if f.status == "CONFIRMED"]
    for i, f in enumerate(confirmed):
        if progress_cb:
            progress_cb("resolve", 0.75 + 0.15 * (i / max(1, len(confirmed))), f"Resolving {f.id}")
        res = resolve(
            f,
            chunk_text_by_id.get(f.chunk_id, ""),
            vector_store=vs,
            graph=graph,
            disable_citation_judge=disable_citation_judge,
        )
        resolutions.append(res)
        if res.verdict != "RESOLVED":
            rw = rewrite(f, chunk_text_by_id.get(f.chunk_id, ""), res, disable_ground_verify=disable_ground_verify)
            if rw is not None:
                rewrites.append(rw)
    pd.DataFrame([r.model_dump() for r in resolutions]).to_csv(rd / "resolutions.csv", index=False)
    pd.DataFrame([r.model_dump() for r in rewrites]).to_csv(rd / "rewrites.csv", index=False)

    tick("done", 1.0, "Pipeline complete")
    per_cat = {c: sum(1 for f in flags if f.category == c and f.status == "CONFIRMED") for c in config.ENABLED_CATEGORIES}
    result = PipelineResult(
        run_id=run_id,
        doc_ids=sorted({p.doc_id for p in pages}),
        n_chunks=len(chunks),
        n_flags_confirmed=sum(1 for f in flags if f.status == "CONFIRMED"),
        n_flags_review=sum(1 for f in flags if f.status == "REVIEW_QUEUE"),
        n_resolutions=len(resolutions),
        n_rewrites=len(rewrites),
        elapsed_seconds=time.time() - t0,
        per_category_counts=per_cat,
        artifact_paths={
            "parse_report": str(rd / "parse_report.json"),
            "chunks": str(rd / "chunks.csv"),
            "flags": str(rd / "flags.csv"),
            "resolutions": str(rd / "resolutions.csv"),
            "rewrites": str(rd / "rewrites.csv"),
            "graph": str(rd / "graph.json"),
            "llm_calls": str(rd / "llm_calls.jsonl"),
        },
    )
    (rd / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def load_pipeline_result(run_id: str) -> dict:
    rd = Path(config.OUTPUT_DIR) / run_id
    out: dict = {}
    for name in ["result.json", "parse_report.json", "graph.json"]:
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
    return out


def list_runs() -> list[str]:
    d = Path(config.OUTPUT_DIR)
    if not d.exists():
        return []
    return sorted([p.name for p in d.iterdir() if p.is_dir() and (p / "result.json").exists()], reverse=True)
