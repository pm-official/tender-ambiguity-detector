"""Stage 2 — hybrid retrieval router + adjudication + LLM-as-judge citation verification (G3).

Prompt-4 update:
- Local categories (F/B/I/A/E/J) → package-wide vector retrieval (across all uploaded docs).
- G/H → graph retrieval (unchanged).
- New adjudication prompt (resolution_package.txt) emits CONFIRMED_AMBIGUOUS / RESOLVED_BY_CONTEXT / PARTIALLY_RESOLVED.
- Legacy vocabulary (RESOLVED / PARTIALLY_RESOLVED / UNRESOLVED) stays accepted by the schema.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from . import config, explain
from .embeddings import VectorStore
from .graph_retriever import graph_facts_block, retrieve_for_flag
from .graph_store import GraphStore
from .schemas import DualScoredFlag, FlagCluster, RetrievedContext, Resolution
from .utils import call_llm, logger, render


class _AdjResp(BaseModel):
    verdict: str = "CONFIRMED_AMBIGUOUS"
    reasoning: str = ""
    cited_context_ids: list[str] = Field(default_factory=list)


class _JudgeResp(BaseModel):
    valid_ids: list[str] = Field(default_factory=list)
    stripped_ids: list[str] = Field(default_factory=list)
    needs_re_adjudication: bool = False


# Accepted / normalised verdicts
_VERDICT_MAP = {
    "CONFIRMED_AMBIGUOUS": "CONFIRMED_AMBIGUOUS",
    "RESOLVED_BY_CONTEXT": "RESOLVED_BY_CONTEXT",
    "PARTIALLY_RESOLVED": "PARTIALLY_RESOLVED",
    # legacy synonyms
    "UNRESOLVED": "CONFIRMED_AMBIGUOUS",
    "RESOLVED": "RESOLVED_BY_CONTEXT",
}


def _contexts_block(contexts: list[RetrievedContext]) -> str:
    if not contexts:
        return "(no context retrieved)"
    return "\n\n".join(
        f"[id={c.context_id}] (score={c.score:.2f}, source={c.source})\n{c.text[:800]}" for c in contexts
    )


def _flag_adapter(flag):
    """Accept either DualScoredFlag or FlagCluster — return a dict with the common fields."""
    if isinstance(flag, DualScoredFlag):
        return {
            "id": flag.id,
            "chunk_id": flag.chunk_id,
            "category": flag.category,
            "span_text": flag.span_text,
            "justification": flag.justification,
            "package_id": flag.package_id,
        }
    return {
        "id": flag.id,
        "chunk_id": flag.chunk_id,
        "category": flag.category,
        "span_text": flag.span_text,
        "justification": "; ".join(p.justification for p in getattr(flag, "passes", [])),
        "package_id": None,
    }


def resolve(
    flag,
    chunk_text: str,
    *,
    vector_store: Optional[VectorStore] = None,
    graph: Optional[GraphStore] = None,
    disable_citation_judge: bool = False,
) -> Resolution:
    f = _flag_adapter(flag)
    cat = f["category"]

    if cat in config.GRAPH_CATEGORIES:
        contexts = retrieve_for_flag(flag, graph) if graph is not None else []
        prompt = render(
            "resolution_graph.txt",
            CATEGORY=cat,
            CATEGORY_NAME=explain.category_display(cat),
            SPAN_TEXT=f["span_text"],
            CHUNK_TEXT=chunk_text,
            GRAPH_FACTS_BLOCK=graph_facts_block(flag, graph) if graph is not None else "(no graph)",
            CONTEXTS_BLOCK=_contexts_block(contexts),
        )
    else:
        query = f"{explain.category_display(cat)}: {f['span_text']} — {chunk_text[:300]}"
        if vector_store is None:
            contexts = []
        else:
            # Package-wide retrieval: prefer the chunk's package, fall back to legacy tender+IS path
            pkg_id = f.get("package_id")
            if pkg_id:
                contexts = vector_store.query_package(query, top_k=config.TOP_K_TENDER, package_id=pkg_id)
            else:
                contexts = vector_store.query_tender(query, top_k=config.TOP_K_TENDER)
        prompt = render(
            "resolution_package.txt",
            CATEGORY_DISPLAY_NAME=explain.category_display(cat),
            SPAN_TEXT=f["span_text"],
            CHUNK_TEXT=chunk_text,
            JUSTIFICATION=f.get("justification", ""),
            RETRIEVED_CONTEXTS=_contexts_block(contexts),
        )

    try:
        adj, _ = call_llm(
            model=config.ADJUDICATION_MODEL,
            prompt=prompt,
            stage="resolve",
            response_schema=_AdjResp,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("adjudication failed flag=%s: %s", f["id"], e)
        return Resolution(
            flag_id=f["id"],
            verdict="CONFIRMED_AMBIGUOUS",
            reasoning=f"(adjudicator failure: {e})",
            cited_context_ids=[],
            retrieved=contexts,
            stage="package_context",
        )

    verdict = _VERDICT_MAP.get(adj.verdict.upper().strip(), "CONFIRMED_AMBIGUOUS")
    resolution = Resolution(
        flag_id=f["id"],
        verdict=verdict,  # type: ignore[arg-type]
        reasoning=adj.reasoning,
        cited_context_ids=list(adj.cited_context_ids),
        retrieved=contexts,
        stage="package_context",
    )

    if not disable_citation_judge and contexts and adj.cited_context_ids:
        resolution = llm_judge_citations(resolution, contexts, prompt)

    return resolution


def llm_judge_citations(resolution: Resolution, contexts: list[RetrievedContext], original_prompt: str) -> Resolution:
    ctx_ids = {c.context_id for c in contexts}
    prompt = render(
        "llm_judge_citation.txt",
        VERDICT=resolution.verdict,
        REASONING=resolution.reasoning,
        CITED_IDS=", ".join(resolution.cited_context_ids),
        CONTEXTS_BLOCK=_contexts_block(contexts),
    )
    try:
        judge, _ = call_llm(
            model=config.JUDGE_MODEL,
            prompt=prompt,
            stage="judge_citations",
            response_schema=_JudgeResp,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning("judge failed flag=%s: %s", resolution.flag_id, e)
        return resolution

    valid = [cid for cid in resolution.cited_context_ids if cid in ctx_ids and cid in judge.valid_ids]
    stripped = [cid for cid in resolution.cited_context_ids if cid not in valid]
    resolution.cited_context_ids = valid
    resolution.judge_stripped = stripped
    if judge.needs_re_adjudication and valid:
        strict_prompt = original_prompt + "\n\nIMPORTANT: Cite ONLY from the block above. Do not invent IDs."
        try:
            adj2, _ = call_llm(
                model=config.ADJUDICATION_MODEL,
                prompt=strict_prompt,
                stage="resolve_retry",
                response_schema=_AdjResp,
                temperature=0.0,
            )
            v = _VERDICT_MAP.get(adj2.verdict.upper().strip())
            if v:
                resolution.verdict = v  # type: ignore[assignment]
                resolution.reasoning = adj2.reasoning
                resolution.cited_context_ids = [cid for cid in adj2.cited_context_ids if cid in ctx_ids]
        except Exception as e:
            logger.warning("re-adjudication failed: %s", e)
            resolution.needs_re_adjudication = True
    return resolution
