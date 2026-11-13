"""Dense retrieval: SentenceTransformers bi-encoder + Qdrant (server or embedded local mode)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Protocol

from app.config import get_settings
from app.knowledge.schemas import Chunk, RetrievalFilter

log = logging.getLogger(__name__)
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    name: str

    def embed_docs(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # lazy: heavy import

        self.name = model_name
        self._model = SentenceTransformer(model_name)
        self._query_prefix = _BGE_QUERY_PREFIX if "bge" in model_name.lower() else ""

    def embed_docs(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(self._query_prefix + text, normalize_embeddings=True).tolist()


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def make_client() -> Any:
    from qdrant_client import QdrantClient

    s = get_settings()
    if s.qdrant_url:
        return QdrantClient(url=s.qdrant_url)
    from pathlib import Path

    Path(s.qdrant_path).mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=s.qdrant_path)


class DenseIndex:
    def __init__(self, embedder: Embedder, client: Any | None = None, collection: str | None = None):
        s = get_settings()
        self.embedder = embedder
        self.client = client or make_client()
        self.collection = collection or s.qdrant_collection

    def rebuild(self, chunks: list[Chunk]) -> int:
        from qdrant_client import models as qm

        vectors = self.embedder.embed_docs([c.index_text() for c in chunks])
        dim = len(vectors[0])
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            self.collection, vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        points = [
            qm.PointStruct(
                id=_point_id(c.chunk_id), vector=v,
                payload={"chunk_id": c.chunk_id, "embedding_model": self.embedder.name,
                         "authority": c.authority, "level": c.level, "version": c.document_version,
                         "success_criterion": c.success_criterion, "document_id": c.document_id},
            )
            for c, v in zip(chunks, vectors)
        ]
        self.client.upsert(self.collection, points=points)
        return len(points)

    def indexed_model(self) -> str | None:
        if not self.client.collection_exists(self.collection):
            return None
        pts, _ = self.client.scroll(self.collection, limit=1, with_payload=True)
        return pts[0].payload.get("embedding_model") if pts else None

    def search(self, query: str, flt: RetrievalFilter, top_k: int = 20) -> list[tuple[str, float]]:
        from qdrant_client import models as qm

        if not self.client.collection_exists(self.collection):
            return []
        must: list[Any] = [qm.FieldCondition(key="level", match=qm.MatchAny(any=[*flt.levels, ""]))]
        if flt.authorities:
            must.append(qm.FieldCondition(key="authority", match=qm.MatchAny(any=flt.authorities)))
        if flt.success_criteria:
            must.append(qm.FieldCondition(key="success_criterion", match=qm.MatchAny(any=flt.success_criteria)))
        res = self.client.query_points(
            self.collection, query=self.embedder.embed_query(query), limit=top_k,
            query_filter=qm.Filter(must=must), with_payload=True,
        )
        return [(p.payload["chunk_id"], float(p.score)) for p in res.points]
