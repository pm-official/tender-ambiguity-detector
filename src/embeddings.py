"""ChromaDB wrapper with text-embedding-004. Two collections: tender_chunks, is_code_chunks."""
from __future__ import annotations

import logging
from typing import Iterable

import chromadb
from chromadb.config import Settings

from . import config
from .schemas import Chunk, RetrievedContext

logger = logging.getLogger("tad.embeddings")


# ---------------------------------------------------------------------------
# Gemini embedding function (Chroma-compatible callable)
# ---------------------------------------------------------------------------


class GeminiEmbeddingFunction:
    name_ = "gemini-text-embedding-004"

    def __init__(self, model: str = config.EMBEDDING_MODEL, task_type: str = "RETRIEVAL_DOCUMENT"):
        self.model = model
        self.task_type = task_type

    def name(self) -> str:  # chroma>=0.5 checks this
        return self.name_

    def __call__(self, input: list[str]) -> list[list[float]]:  # chroma API
        import google.generativeai as genai

        if not hasattr(self, "_configured"):
            genai.configure(api_key=config.GOOGLE_API_KEY)
            self._configured = True

        embeddings: list[list[float]] = []
        for txt in input:
            try:
                r = genai.embed_content(model=self.model, content=txt[:8000], task_type=self.task_type)
                emb = r["embedding"] if isinstance(r, dict) else r.embedding  # type: ignore[attr-defined]
                embeddings.append(list(emb))
            except Exception as e:
                logger.warning("embed failed for text[%d]: %s — using zero vector", len(txt), e)
                embeddings.append([0.0] * 768)
        return embeddings


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class VectorStore:
    def __init__(self, persist_dir: str | None = None):
        persist_dir = persist_dir or str(config.CHROMA_DIR)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.emb_doc = GeminiEmbeddingFunction(task_type="RETRIEVAL_DOCUMENT")
        self.emb_query = GeminiEmbeddingFunction(task_type="RETRIEVAL_QUERY")
        self.tender = self.client.get_or_create_collection(
            "tender_chunks",
            embedding_function=self.emb_doc,
            metadata={"hnsw:space": "cosine"},
        )
        self.is_code = self.client.get_or_create_collection(
            "is_code_chunks",
            embedding_function=self.emb_doc,
            metadata={"hnsw:space": "cosine"},
        )

    def reset_tender(self):
        try:
            self.client.delete_collection("tender_chunks")
        except Exception:
            pass
        self.tender = self.client.get_or_create_collection(
            "tender_chunks",
            embedding_function=self.emb_doc,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: Iterable[Chunk], *, collection: str = "tender") -> int:
        target = self.tender if collection == "tender" else self.is_code
        ids = [c.id for c in chunks]
        docs = [c.text for c in chunks]
        metas = [
            {"doc_id": c.doc_id, "page": c.page, "clause_hint": c.clause_hint or "", "char_start": c.char_start}
            for c in chunks
        ]
        if not ids:
            return 0
        # Chroma errors if id already present; upsert
        target.upsert(ids=ids, documents=docs, metadatas=metas)
        return len(ids)

    def query_tender(self, query: str, top_k: int = 5) -> list[RetrievedContext]:
        return self._query(self.tender, query, top_k, source="tender")

    def query_is_code(self, query: str, top_k: int = 5) -> list[RetrievedContext]:
        return self._query(self.is_code, query, top_k, source="is_code")

    def query_both(self, query: str, top_k_tender: int, top_k_iscode: int) -> list[RetrievedContext]:
        return self.query_tender(query, top_k_tender) + self.query_is_code(query, top_k_iscode)

    def _query(self, coll, query: str, top_k: int, *, source: str) -> list[RetrievedContext]:
        if coll.count() == 0:
            return []
        q_emb = self.emb_query([query])
        res = coll.query(query_embeddings=q_emb, n_results=min(top_k, coll.count()))
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0] if res.get("distances") else [0.0] * len(ids)
        out: list[RetrievedContext] = []
        for i, d, m, dist in zip(ids, docs, metas, dists):
            out.append(
                RetrievedContext(
                    context_id=f"{source}:{i}",
                    source="tender" if source == "tender" else "is_code",
                    text=d,
                    score=float(1.0 - dist) if dist is not None else 0.0,
                    meta=m or {},
                )
            )
        return out
