"""Retrieve cross-document context for G and H flags from the knowledge graph."""
from __future__ import annotations

from .graph_store import GraphStore
from .schemas import FlagCluster, RetrievedContext


def retrieve_for_flag(flag: FlagCluster, graph: GraphStore) -> list[RetrievedContext]:
    if graph is None:
        return []
    out: list[RetrievedContext] = []
    g = graph.g

    # Clause text itself
    if g.has_node(flag.chunk_id):
        nd = g.nodes[flag.chunk_id]
        out.append(
            RetrievedContext(
                context_id=f"graph:clause:{flag.chunk_id}",
                source="graph",
                text=nd.get("text", ""),
                score=1.0,
                meta={"kind": "CLAUSE", "doc_id": nd.get("doc_id"), "clause_hint": nd.get("clause_hint")},
            )
        )

    if flag.category == "H":
        # Find any quantities mentioned by this chunk, then find other chunks sharing that name.
        for _, nbr, k, d in g.out_edges(flag.chunk_id, keys=True, data=True):
            if d.get("kind") == "MENTIONS" and g.nodes[nbr].get("kind") == "QUANTITY":
                qname = g.nodes[nbr].get("name")
                for qn, qd in g.nodes(data=True):
                    if qd.get("kind") == "QUANTITY" and qd.get("name") == qname and qn != nbr:
                        out.append(
                            RetrievedContext(
                                context_id=f"graph:quantity:{qn}",
                                source="graph",
                                text=f"{qd.get('name')}: value {qd.get('value')} {qd.get('unit')} (raw: '{qd.get('raw_text')}')",
                                score=0.95,
                                meta={"kind": "QUANTITY", "name": qd.get("name"), "value": qd.get("value"), "unit": qd.get("unit")},
                            )
                        )

    if flag.category == "G":
        for n, d in g.nodes(data=True):
            if d.get("kind") == "PRIORITY_RULE":
                out.append(
                    RetrievedContext(
                        context_id=f"graph:priority:{n}",
                        source="graph",
                        text=d.get("raw_text", ""),
                        score=0.90,
                        meta={"kind": "PRIORITY_RULE"},
                    )
                )

    return out


def graph_facts_block(flag: FlagCluster, graph: GraphStore) -> str:
    ctx = retrieve_for_flag(flag, graph)
    if not ctx:
        return "(no cross-document graph facts found)"
    lines = []
    for c in ctx:
        lines.append(f"[{c.context_id}] {c.text[:400]}")
    return "\n".join(lines)
