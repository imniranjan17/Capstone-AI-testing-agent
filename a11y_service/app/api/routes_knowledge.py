from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import set_graph
from app.config import get_settings
from app.knowledge import loader
from app.retrieval.service import reset_retriever

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
log = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    directory: str = ""  # relative to the approved knowledge directory
    rebuild_dense: bool = True


def rebuild_indexes(rebuild_dense: bool = True) -> dict:
    """Reload chunks and (optionally) rebuild the Qdrant collection. Returns status info."""
    status: dict = {"dense": "skipped"}
    reset_retriever()
    set_graph(None)
    chunks = loader.load_chunks()
    status["chunks"] = len(chunks)
    if rebuild_dense and chunks and get_settings().retrieval_enabled:
        try:
            from app.retrieval.dense_index import DenseIndex, SentenceTransformerEmbedder

            n = DenseIndex(SentenceTransformerEmbedder(get_settings().embed_model)).rebuild(chunks)
            status["dense"] = f"indexed {n} vectors"
        except Exception as exc:
            status["dense"] = f"unavailable: {exc}"
    return status


@router.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    root = Path(get_settings().knowledge_dir).resolve()
    target = (root / req.directory).resolve()
    if root != target and root not in target.parents:
        raise HTTPException(status_code=400, detail="Directory must be inside the approved knowledge directory")
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    chunks, errors = loader.ingest_paths(loader.discover(target))
    return {"ingested_chunks": len(chunks), "rejected": errors, **rebuild_indexes(req.rebuild_dense)}


@router.delete("/documents/{document_id}")
def delete_document(document_id: str) -> dict:
    removed = loader.delete_document(document_id)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"removed_chunks": removed, **rebuild_indexes(True)}
