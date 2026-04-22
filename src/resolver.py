"""Hybrid retrieval router + adjudication + LLM-as-judge citation verification."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from . import config
from .embeddings import VectorStore
from .graph_retriever import graph_facts_block, retrieve_for_flag
from .graph_store import GraphStore
from .schemas import FlagCluster, RetrievedContext, Resolution
from .utils import call_llm, logger, render


class _AdjResp(BaseModel):
    verdict: str = "UNRESOLVED"
    reasoning: str = ""
    cited_context_ids: list[str] = Field(default_factory=list)


class _JudgeResp(BaseModel):
    valid_ids: list[str] = Field(default_factory=list)
    stripped_ids: list[str] = Field(default_factory=list)
    needs_re_adjudication: bool = False


VERDICTS = {"RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED"}


def _contexts_block(contexts: list[RetrievedContext]) -> str:
    if not contexts:
        return "(no context retrieved)"
    return "\n\n".join(f"[id={c.context_id}] (score={c.score:.2f}, source={c.source})\n{c.text[:800]}" for c in contexts)


def resolve(
    flag: FlagCluster,
    chunk_text: str,
    *,
    vector_store: VectorStore | None = None,
    graph: GraphStore | None = None,
    disable_citation_judge: bool = False,
) -> Resolution:
    if flag.category in config.GRAPH_CATEGORIES:
        contexts = retrieve_for_flag(flag, graph) if graph is not None else []
        prompt = render(
            "resolution_graph.txt",
            CATEGORY=flag.category,
            CATEGORY_NAME=config.CATEGORY_NAMES[flag.category],
            SPAN_TEXT=flag.span_text,
            CHUNK_TEXT=chunk_text,
            GRAPH_FACTS_BLOCK=graph_facts_block(flag, graph) if graph is not None else "(no graph)",
            CONTEXTS_BLOCK=_contexts_block(contexts),
        )
    else:
        query = f"{config.CATEGORY_NAMES[flag.category]}: {flag.span_text} — {chunk_text[:300]}"
        if vector_store is None:
            contexts = []
        else:
            contexts = vector_store.query_both(query, config.TOP_K_TENDER, config.TOP_K_ISCODE)
        prompt = render(
            "resolution.txt",
            CATEGORY=flag.category,
            CATEGORY_NAME=config.CATEGORY_NAMES[flag.category],
            SPAN_TEXT=flag.span_text,
            CHUNK_TEXT=chunk_text,
            CONTEXTS_BLOCK=_contexts_block(contexts),
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
        logger.warning("adjudication failed flag=%s: %s", flag.id, e)
        return Resolution(
            flag_id=flag.id,
            verdict="UNRESOLVED",
            reasoning=f"(adjudicator failure: {e})",
            cited_context_ids=[],
            retrieved=contexts,
        )

    verdict = adj.verdict if adj.verdict in VERDICTS else "UNRESOLVED"
    resolution = Resolution(
        flag_id=flag.id,
        verdict=verdict,  # type: ignore[arg-type]
        reasoning=adj.reasoning,
        cited_context_ids=list(adj.cited_context_ids),
        retrieved=contexts,
    )

    # G3 — citation judge
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
        # one re-run with stricter wording
        strict_prompt = original_prompt + "\n\nIMPORTANT: Cite ONLY from the block above. Do not invent IDs."
        try:
            class _R(_AdjResp):
                pass
            adj2, _ = call_llm(
                model=config.ADJUDICATION_MODEL,
                prompt=strict_prompt,
                stage="resolve_retry",
                response_schema=_R,
                temperature=0.0,
            )
            if adj2.verdict in VERDICTS:
                resolution.verdict = adj2.verdict  # type: ignore[assignment]
                resolution.reasoning = adj2.reasoning
                resolution.cited_context_ids = [cid for cid in adj2.cited_context_ids if cid in ctx_ids]
        except Exception as e:
            logger.warning("re-adjudication failed: %s", e)
            resolution.needs_re_adjudication = True
    return resolution
