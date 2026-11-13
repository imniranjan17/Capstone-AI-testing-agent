"""Hybrid retrieval: BM25 (sparse) + bi-encoder (dense) fused with Reciprocal Rank Fusion.

Pattern follows RAG-Handson (bm25_index / dense_index / rrf). Metadata filters are applied BEFORE ranking.
Dense is optional: if the model can't load, search degrades to BM25-only (status reports it).
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import settings
from app.rag.docs import Doc, build_docs

log = logging.getLogger(__name__)
_TOKEN = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")
_BGE_Q = "Represent this sentence for searching relevant passages: "


def tokenize(text: str) -> list[str]:
    toks = _TOKEN.findall(text.lower())
    extra = [p for t in toks if "-" in t or "." in t for p in re.split(r"[-.]", t) if p]
    return toks + extra


def rrf_fuse(sparse: list[tuple[str, float]], dense: list[tuple[str, float]], k: int = 60,
             top_n: int = 20) -> list[dict[str, Any]]:
    """Ranked (doc_id, score) lists in, fused + deduplicated out, with per-retriever provenance."""
    fused: dict[str, dict[str, Any]] = {}
    for name, ranked in (("sparse", sparse), ("dense", dense)):
        for rank, (did, score) in enumerate(ranked, start=1):
            e = fused.setdefault(did, {"doc_id": did, "sparse_rank": None, "dense_rank": None,
                                       "sparse_score": None, "dense_score": None, "rrf_score": 0.0})
            e[f"{name}_rank"], e[f"{name}_score"] = rank, score
            e["rrf_score"] += 1.0 / (k + rank)
    return sorted(fused.values(), key=lambda e: (-e["rrf_score"], e["doc_id"]))[:top_n]


class Embedder(Protocol):
    def embed_docs(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # lazy, heavy
        self._m = SentenceTransformer(model_name)
        self._prefix = _BGE_Q if "bge" in model_name.lower() else ""

    def embed_docs(self, texts):
        return self._m.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text):
        return self._m.encode(self._prefix + text, normalize_embeddings=True).tolist()


class HybridRetriever:
    def __init__(self, embedder: Embedder | None = None, use_dense: bool | None = None,
                 db_path: str | None = None):
        self.db_path = db_path
        self.use_dense = settings.dense_enabled if use_dense is None else use_dense
        self._embedder = embedder
        self._vec: dict[str, np.ndarray] = {}      # sha1(text) -> vector (embed each text once)
        self.status = {"sparse": "ok", "dense": "pending" if self.use_dense else "disabled"}

    def _get_embedder(self) -> Embedder | None:
        if self._embedder is None and self.use_dense:
            try:
                self._embedder = SentenceTransformerEmbedder(settings.embed_model)
            except Exception as e:  # no model / no network -> BM25-only
                log.warning("dense retrieval unavailable: %s", e)
                self.use_dense, self.status["dense"] = False, f"unavailable ({e.__class__.__name__})"
        return self._embedder

    def _dense_search(self, docs: list[Doc], query: str, top_k: int) -> list[tuple[str, float]]:
        emb = self._get_embedder()
        if emb is None or not docs:
            return []
        hashes = [hashlib.sha1(d.text.encode()).hexdigest() for d in docs]
        todo = [(h, d.text) for h, d in zip(hashes, docs) if h not in self._vec]
        if todo:
            for (h, _), v in zip(todo, emb.embed_docs([t for _, t in todo])):
                self._vec[h] = np.asarray(v, dtype=np.float32)
        q = np.asarray(emb.embed_query(query), dtype=np.float32)
        scores = np.stack([self._vec[h] for h in hashes]) @ q
        order = np.argsort(-scores)[:top_k]
        self.status["dense"] = "ok"
        return [(docs[i].doc_id, float(scores[i])) for i in order]

    def search(self, query: str, domain: str | None = None, top_k: int = 8, pool: int = 30) -> list[dict]:
        docs = build_docs(self.db_path, domain)            # filter first, then rank
        if not docs:
            return []
        by_id = {d.doc_id: d for d in docs}
        bm = BM25Okapi([tokenize(d.text) for d in docs])
        sc = bm.get_scores(tokenize(query))
        sparse = sorted(((d.doc_id, float(s)) for d, s in zip(docs, sc) if s > 0), key=lambda x: (-x[1], x[0]))[:pool]
        dense = self._dense_search(docs, query, pool) if self.use_dense else []
        out = []
        for e in rrf_fuse(sparse, dense, top_n=top_k):
            d = by_id[e["doc_id"]]
            out.append({**e, "text": d.text, "meta": d.meta})
        return out
