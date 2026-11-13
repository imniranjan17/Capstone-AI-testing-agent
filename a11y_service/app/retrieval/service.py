"""Hybrid retrieval orchestration with graceful degradation.

Pipeline: BM25 + dense -> RRF -> cross-encoder. Each neural stage is optional; if it cannot be
loaded the stage is skipped and recorded in `status`, so deterministic results are still returned.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import get_settings
from app.knowledge.loader import load_chunks
from app.knowledge.schemas import Chunk, RetrievalFilter
from app.retrieval.bm25_index import BM25Index
from app.retrieval.reranker import Scorer, rerank
from app.retrieval.rrf import rrf_fuse

log = logging.getLogger(__name__)


class Retriever:
    def __init__(self, chunks: list[Chunk], dense: Any | None = None, scorer: Scorer | None = None):
        s = get_settings()
        self.settings = s
        self.chunks = chunks
        self.by_id = {c.chunk_id: c for c in chunks}
        self.bm25 = BM25Index(chunks)
        self.dense = dense
        self.scorer = scorer
        self.status = {
            "chunks": len(chunks), "bm25": bool(chunks),
            "dense": dense is not None, "reranker": scorer is not None,
        }

    @classmethod
    def from_settings(cls) -> "Retriever":
        s = get_settings()
        chunks = load_chunks()
        dense = scorer = None
        if s.retrieval_enabled and chunks:
            try:
                from app.retrieval.dense_index import DenseIndex, SentenceTransformerEmbedder

                dense = DenseIndex(SentenceTransformerEmbedder(s.embed_model))
                if dense.indexed_model() is None:
                    dense = None
                    log.warning("Dense index not built; run scripts/build_indexes.py")
                elif dense.indexed_model() != s.embed_model:
                    log.warning("Dense index was built with a different model; rebuild required")
                    dense = None
            except Exception as exc:
                log.warning("Dense retrieval unavailable: %s", exc)
            try:
                from app.retrieval.reranker import CrossEncoderScorer

                scorer = CrossEncoderScorer(s.rerank_model)
            except Exception as exc:
                log.warning("Reranker unavailable: %s", exc)
        return cls(chunks, dense, scorer)

    def lookup(self, criteria: list[str]) -> list[Chunk]:
        """Local, versioned lookup of normative chunks by criterion ID (no ranking)."""
        want = set(criteria)
        return [c for c in self.chunks if c.authority == "normative" and c.success_criterion in want]

    def sparse(self, text: str, flt: RetrievalFilter) -> list[tuple[str, float]]:
        return self.bm25.search(text, flt, self.settings.sparse_top_k)

    def dense_search(self, text: str, flt: RetrievalFilter) -> list[tuple[str, float]]:
        if self.dense is None:
            return []
        try:
            return self.dense.search(text, flt, self.settings.dense_top_k)
        except Exception as exc:
            log.warning("Dense search failed: %s", exc)
            return []

    def fuse(self, sparse: list[tuple[str, float]], dense: list[tuple[str, float]]) -> list[dict[str, Any]]:
        return rrf_fuse(sparse, dense, self.settings.rrf_k, top_n=20)

    def rerank(self, text: str, fused: list[dict[str, Any]]) -> list[tuple[Chunk, float]]:
        k = self.settings.rerank_top_k
        candidates = [self.by_id[f["chunk_id"]] for f in fused if f["chunk_id"] in self.by_id]
        if self.scorer is not None and candidates:
            try:
                return rerank(text, candidates, self.scorer, k)
            except Exception as exc:
                log.warning("Rerank failed: %s", exc)
        scores = {f["chunk_id"]: f["rrf_score"] for f in fused}
        return [(c, scores[c.chunk_id]) for c in candidates[:k]]

    def search(self, query: dict[str, Any], flt: RetrievalFilter | None = None) -> dict[str, Any]:
        flt = flt or RetrievalFilter()
        text = query["text"]
        sparse = self.sparse(text, flt)
        dense = self.dense_search(text, flt)
        fused = self.fuse(sparse, dense)
        return {"results": self.rerank(text, fused), "sparse": sparse, "dense": dense, "fused": fused}


_lock = threading.Lock()
_instance: Retriever | None = None


def get_retriever() -> Retriever:
    global _instance
    with _lock:
        if _instance is None:
            _instance = Retriever.from_settings()
        return _instance


def reset_retriever(instance: Retriever | None = None) -> None:
    global _instance
    with _lock:
        _instance = instance
