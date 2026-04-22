"""ChromaDB wrapper with text-embedding-004.

Collections:
- tender_package_chunks : all chunks from uploaded tender packages (Prompt-4 primary).
- standards_chunks      : IS-code + CPWD spec chunks (Prompt-4 standards corpus).
- tender_chunks         : legacy single-document collection (Prompt-3).
- is_code_chunks        : legacy IS-code collection (Prompt-3) — mirrored by standards_chunks.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

import chromadb
from chromadb.config import Settings

from . import config
from .schemas import Chunk, RetrievedContext

logger = logging.getLogger("tad.embeddings")


class GeminiEmbeddingFunction:
    name_ = "gemini-text-embedding-004"

    def __init__(self, model: str = config.EMBEDDING_MODEL, task_type: str = "RETRIEVAL_DOCUMENT"):
        self.model = model
        self.task_type = task_type

    def name(self) -> str:
        return self.name_

    def __call__(self, input: list[str]) -> list[list[float]]:
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


class VectorStore:
    def __init__(self, persist_dir: str | None = None):
        persist_dir = persist_dir or str(config.CHROMA_DIR)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.emb_doc = GeminiEmbeddingFunction(task_type="RETRIEVAL_DOCUMENT")
        self.emb_query = GeminiEmbeddingFunction(task_type="RETRIEVAL_QUERY")
        # Primary Prompt-4 collections
        self.package = self.client.get_or_create_collection(
            "tender_package_chunks",
            embedding_function=self.emb_doc,
            metadata={"hnsw:space": "cosine"},
        )
        self.standards = self.client.get_or_create_collection(
            "standards_chunks",
            embedding_function=self.emb_doc,
            metadata={"hnsw:space": "cosine"},
        )
        # Legacy collections (Prompt-3)
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

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    def reset_package(self, package_id: str | None = None):
        """Reset the whole package collection, or only chunks with a specific package_id."""
        if package_id is None:
            try:
                self.client.delete_collection("tender_package_chunks")
            except Exception:
                pass
            self.package = self.client.get_or_create_collection(
                "tender_package_chunks",
                embedding_function=self.emb_doc,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            try:
                self.package.delete(where={"package_id": package_id})
            except Exception as e:
                logger.warning("package_id reset failed: %s", e)

    def reset_tender(self):  # legacy
        try:
            self.client.delete_collection("tender_chunks")
        except Exception:
            pass
        self.tender = self.client.get_or_create_collection(
            "tender_chunks",
            embedding_function=self.emb_doc,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------
    def _collection(self, name: str):
        return {
            "package": self.package,
            "standards": self.standards,
            "tender": self.tender,
            "is_code": self.is_code,
        }[name]

    def add_chunks(self, chunks: Iterable[Chunk], *, collection: str = "package") -> int:
        """Add chunks to one of: package / standards / tender / is_code."""
        target = self._collection(collection)
        chunks = list(chunks)
        if not chunks:
            return 0
        ids = [c.id for c in chunks]
        docs = [c.text for c in chunks]
        metas = []
        for c in chunks:
            m = {
                "doc_id": c.doc_id,
                "page": c.page,
                "clause_hint": c.clause_hint or "",
                "char_start": c.char_start,
            }
            if c.package_id:
                m["package_id"] = c.package_id
            if c.document_type:
                m["document_type"] = c.document_type
            metas.append(m)
        target.upsert(ids=ids, documents=docs, metadatas=metas)
        return len(ids)

    def add_standards_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        source_type: str = "IS",
        topic: str | None = None,
    ) -> int:
        chunks = list(chunks)
        if not chunks:
            return 0
        ids = [c.id for c in chunks]
        docs = [c.text for c in chunks]
        metas = [
            {
                "doc_id": c.doc_id,
                "page": c.page,
                "clause_hint": c.clause_hint or "",
                "char_start": c.char_start,
                "source_type": source_type,
                "topic": topic or "",
            }
            for c in chunks
        ]
        self.standards.upsert(ids=ids, documents=docs, metadatas=metas)
        return len(ids)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def query_package(
        self,
        query: str,
        top_k: int = 5,
        package_id: str | None = None,
        doc_type_filter: Optional[str] = None,
    ) -> list[RetrievedContext]:
        where = {}
        if package_id:
            where["package_id"] = package_id
        if doc_type_filter:
            where["document_type"] = doc_type_filter
        return self._query(self.package, query, top_k, source="tender", where=where or None)

    def query_standards(
        self,
        query: str,
        top_k: int = 5,
        topic_filter: Optional[str] = None,
    ) -> list[RetrievedContext]:
        where = None
        if topic_filter:
            where = {"topic": topic_filter}
        return self._query(self.standards, query, top_k, source="is_code", where=where)

    # Legacy helpers (Prompt-3 callers)
    def query_tender(self, query: str, top_k: int = 5) -> list[RetrievedContext]:
        return self._query(self.tender, query, top_k, source="tender")

    def query_is_code(self, query: str, top_k: int = 5) -> list[RetrievedContext]:
        return self._query(self.is_code, query, top_k, source="is_code")

    def query_both(self, query: str, top_k_tender: int, top_k_iscode: int) -> list[RetrievedContext]:
        return self.query_tender(query, top_k_tender) + self.query_is_code(query, top_k_iscode)

    def _query(self, coll, query: str, top_k: int, *, source: str, where: dict | None = None) -> list[RetrievedContext]:
        if coll.count() == 0:
            return []
        q_emb = self.emb_query([query])
        kwargs = dict(query_embeddings=q_emb, n_results=min(top_k, coll.count()))
        if where:
            kwargs["where"] = where
        try:
            res = coll.query(**kwargs)
        except Exception as e:
            logger.warning("query failed (%s): %s", source, e)
            return []
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
