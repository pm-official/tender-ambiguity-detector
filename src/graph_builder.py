"""Assemble the tender knowledge graph from chunks using LLM extraction."""
from __future__ import annotations

import re
import uuid
from typing import Iterable

from pydantic import BaseModel, Field

from . import config
from .graph_store import GraphStore
from .schemas import Chunk, Entity, PriorityRule, Quantity
from .utils import call_llm, logger, render


class _EntityItem(BaseModel):
    surface: str = ""
    canonical: str = ""
    kind: str = "OTHER"


class _QuantityItem(BaseModel):
    name: str = ""
    value: float | None = None
    unit: str = ""
    raw_text: str = ""


class _EntExtractResp(BaseModel):
    entities: list[_EntityItem] = Field(default_factory=list)
    quantities: list[_QuantityItem] = Field(default_factory=list)


class _PrioRuleItem(BaseModel):
    dominant_doc: str = ""
    subordinate_doc: str = ""
    raw_text: str = ""


class _PrioResp(BaseModel):
    rules: list[_PrioRuleItem] = Field(default_factory=list)


def _canonical_doc_name(raw: str) -> str:
    r = raw.lower().strip()
    r = re.sub(r"\s+", "_", r)
    r = re.sub(r"[^a-z0-9_]", "", r)
    return r or f"doc_{uuid.uuid4().hex[:6]}"


def build_graph(chunks: Iterable[Chunk]) -> GraphStore:
    store = GraphStore()
    chunks = list(chunks)

    # 1) Documents and clauses
    for c in chunks:
        doc_id = _canonical_doc_name(c.doc_id)
        store.add_clause(clause_id=c.id, doc_id=doc_id, text=c.text, clause_hint=c.clause_hint)

    # 2) Entities and quantities per chunk
    entity_cache: dict[str, Entity] = {}
    for c in chunks:
        try:
            resp, _ = call_llm(
                config.EXTRACTION_MODEL,
                render("entity_extraction.txt", CHUNK_TEXT=c.text),
                stage="extract_entities",
                response_schema=_EntExtractResp,
            )
        except Exception as e:
            logger.warning("entity extraction failed chunk=%s: %s", c.id, e)
            continue
        for ent in resp.entities:
            canon = (ent.canonical or ent.surface or "").strip().lower()
            if not canon:
                continue
            if canon in entity_cache:
                e = entity_cache[canon]
                if ent.surface and ent.surface not in e.surface_forms:
                    e.surface_forms.append(ent.surface)
                if c.id not in e.sources:
                    e.sources.append(c.id)
            else:
                e = Entity(
                    id=f"ent_{uuid.uuid4().hex[:8]}",
                    surface_forms=[ent.surface] if ent.surface else [canon],
                    canonical=canon,
                    kind="ENTITY",
                    sources=[c.id],
                )
                entity_cache[canon] = e
        for q in resp.quantities:
            if not q.name:
                continue
            store.add_quantity(
                Quantity(
                    id=f"qty_{uuid.uuid4().hex[:8]}",
                    name=q.name.strip(),
                    value=q.value,
                    unit=q.unit,
                    raw_text=q.raw_text,
                    source_chunk_id=c.id,
                )
            )

    for e in entity_cache.values():
        store.add_entity(e)

    # 3) Priority rules
    for c in chunks:
        try:
            resp, _ = call_llm(
                config.EXTRACTION_MODEL,
                render("priority_rule_extraction.txt", CHUNK_TEXT=c.text),
                stage="extract_priority_rules",
                response_schema=_PrioResp,
            )
        except Exception as e:
            logger.warning("priority extraction failed chunk=%s: %s", c.id, e)
            continue
        for r in resp.rules:
            if not r.dominant_doc or not r.subordinate_doc:
                continue
            store.add_priority_rule(
                PriorityRule(
                    id=f"prio_{uuid.uuid4().hex[:8]}",
                    dominant_doc=_canonical_doc_name(r.dominant_doc),
                    subordinate_doc=_canonical_doc_name(r.subordinate_doc),
                    source_chunk_id=c.id,
                    raw_text=r.raw_text,
                )
            )

    return store
