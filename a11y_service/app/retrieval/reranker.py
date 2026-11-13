"""Cross-encoder reranking with authority preference on near-ties."""
from __future__ import annotations

from typing import Protocol

from app.knowledge.schemas import AUTHORITY_RANK, Chunk

_MAX_CHARS = 1500  # ~ well under the 512-token limit; header is kept at the front
_NEAR_TIE = 0.05


class Scorer(Protocol):
    def score(self, pairs: list[tuple[str, str]]) -> list[float]: ...


class CrossEncoderScorer:
    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder  # lazy: heavy import

        self.name = model_name
        self._model = CrossEncoder(model_name, max_length=512)

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        return [float(x) for x in self._model.predict(pairs)]


def _passage(c: Chunk) -> str:
    # Criterion ID, title, level and text lead the passage so truncation never drops them.
    return c.index_text()[:_MAX_CHARS]


def rerank(
    query: str, candidates: list[Chunk], scorer: Scorer, top_k: int = 5,
) -> list[tuple[Chunk, float]]:
    if not candidates:
        return []
    scores = scorer.score([(query, _passage(c)) for c in candidates])
    scored = list(zip(candidates, scores))
    hi, lo = max(scores), min(scores)
    span = (hi - lo) or 1.0

    def key(item: tuple[Chunk, float]) -> tuple[float, int, str]:
        c, s = item
        norm = (s - lo) / span
        # bucket near-equal scores so higher-authority sources win ties
        return (-round(norm / _NEAR_TIE), AUTHORITY_RANK.get(c.authority, 9), c.chunk_id)

    ranked = sorted(scored, key=key)
    return ranked[:top_k]
