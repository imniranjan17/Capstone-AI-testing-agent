"""Sparse BM25 retrieval with metadata filtering (applied before ranking)."""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from app.knowledge.schemas import Chunk, RetrievalFilter

_TOKEN = re.compile(r"[a-z0-9]+(?:[-.][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    toks = _TOKEN.findall(text.lower())
    extra = []
    for t in toks:  # keep compound tokens (aria-label, 4.1.2) and their parts
        if "-" in t or "." in t:
            extra.extend(p for p in re.split(r"[-.]", t) if p)
    return toks + extra


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._bm25 = BM25Okapi([tokenize(self._doc(c)) for c in chunks]) if chunks else None

    @staticmethod
    def _doc(c: Chunk) -> str:
        return f"{c.success_criterion} {c.title} {c.index_text()}"

    def search(self, query: str, flt: RetrievalFilter, top_k: int = 20) -> list[tuple[str, float]]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(
            ((c.chunk_id, float(s)) for c, s in zip(self.chunks, scores) if flt.matches(c) and s > 0),
            key=lambda x: (-x[1], x[0]),
        )
        return ranked[:top_k]
