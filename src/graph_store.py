"""NetworkX-backed knowledge graph with typed nodes and edges."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from .schemas import Conflict, Entity, PriorityRule, Quantity


class GraphStore:
    def __init__(self):
        self.g = nx.MultiDiGraph()

    # ---------- add nodes ----------
    def add_document(self, doc_id: str, title: str | None = None):
        self.g.add_node(doc_id, kind="DOCUMENT", title=title or doc_id)

    def add_clause(self, clause_id: str, doc_id: str, text: str, clause_hint: str | None = None):
        self.g.add_node(clause_id, kind="CLAUSE", text=text, clause_hint=clause_hint or "", doc_id=doc_id)
        if not self.g.has_node(doc_id):
            self.add_document(doc_id)
        self.g.add_edge(doc_id, clause_id, kind="HAS_CLAUSE")

    def add_entity(self, e: Entity):
        self.g.add_node(e.id, kind="ENTITY", canonical=e.canonical, surface_forms=list(e.surface_forms))
        for src in e.sources:
            self.g.add_edge(src, e.id, kind="MENTIONS")

    def add_quantity(self, q: Quantity):
        self.g.add_node(q.id, kind="QUANTITY", name=q.name, value=q.value, unit=q.unit, raw_text=q.raw_text)
        if q.source_chunk_id and self.g.has_node(q.source_chunk_id):
            self.g.add_edge(q.source_chunk_id, q.id, kind="MENTIONS")

    def add_priority_rule(self, r: PriorityRule):
        self.g.add_node(r.id, kind="PRIORITY_RULE", raw_text=r.raw_text)
        if not self.g.has_node(r.dominant_doc):
            self.add_document(r.dominant_doc)
        if not self.g.has_node(r.subordinate_doc):
            self.add_document(r.subordinate_doc)
        self.g.add_edge(r.id, r.dominant_doc, kind="PRIORITISES_DOMINANT")
        self.g.add_edge(r.id, r.subordinate_doc, kind="PRIORITISES_SUBORDINATE")
        if self.g.has_node(r.source_chunk_id):
            self.g.add_edge(r.source_chunk_id, r.id, kind="MENTIONS")

    def add_conflict_edge(self, q_a: str, q_b: str, description: str):
        self.g.add_edge(q_a, q_b, kind="INCONSISTENT_WITH", description=description)

    # ---------- query ----------
    def nodes_of_kind(self, kind: str) -> list[str]:
        return [n for n, d in self.g.nodes(data=True) if d.get("kind") == kind]

    def quantities(self) -> list[dict]:
        return [{**d, "id": n} for n, d in self.g.nodes(data=True) if d.get("kind") == "QUANTITY"]

    def priority_rules(self) -> list[dict]:
        return [{**d, "id": n} for n, d in self.g.nodes(data=True) if d.get("kind") == "PRIORITY_RULE"]

    def find_numeric_conflicts(self) -> list[Conflict]:
        qs = self.quantities()
        by_name: dict[str, list[dict]] = {}
        for q in qs:
            if q.get("name") and q.get("value") is not None:
                by_name.setdefault(str(q["name"]).lower().strip(), []).append(q)
        out: list[Conflict] = []
        for name, group in by_name.items():
            values = {q["value"] for q in group}
            if len(values) > 1:
                ids = [q["id"] for q in group]
                out.append(
                    Conflict(
                        id=f"conflict_num_{name.replace(' ', '_')[:30]}",
                        kind="NUMERIC",
                        description=f"Quantity '{name}' has differing values: {sorted(values)}",
                        involved_chunks=[],
                        involved_quantities=ids,
                    )
                )
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        self.add_conflict_edge(ids[i], ids[j], f"value mismatch {name}")
        return out

    # ---------- serialise ----------
    def to_json(self) -> dict[str, Any]:
        return {
            "nodes": [{"id": n, **d} for n, d in self.g.nodes(data=True)],
            "edges": [
                {"source": u, "target": v, "key": k, **d}
                for u, v, k, d in self.g.edges(keys=True, data=True)
            ],
        }

    def save_json(self, path: Path):
        path.write_text(json.dumps(self.to_json(), indent=2, default=str), encoding="utf-8")
