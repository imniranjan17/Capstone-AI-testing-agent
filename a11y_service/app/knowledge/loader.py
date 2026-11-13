"""Deterministic ingestion + persisted chunk store (source of truth for BM25 and dense indexes)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.knowledge.chunker import build_criteria_ref, chunk_file
from app.knowledge.schemas import Chunk

log = logging.getLogger(__name__)
SUPPORTED = {".json", ".md", ".txt", ".html", ".htm"}


def _store_path() -> Path:
    return Path(get_settings().sqlite_path).with_name("chunks.jsonl")


def load_chunks() -> list[Chunk]:
    p = _store_path()
    if not p.exists():
        return []
    return [Chunk.model_validate_json(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_chunks(chunks: list[Chunk]) -> None:
    p = _store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(c.model_dump_json() for c in chunks), encoding="utf-8")


def discover(directory: Path) -> list[Path]:
    skip = {"axe_rules.json"}
    return sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED and p.name not in skip and not p.name.endswith(".meta.json")
    )


def ingest_paths(paths: list[Path]) -> tuple[list[Chunk], list[str]]:
    """Chunk files and merge into the store, replacing chunks of any re-ingested document."""
    ref = build_criteria_ref(paths)
    new: list[Chunk] = []
    errors: list[str] = []
    for p in paths:
        try:
            new.extend(chunk_file(p, ref))
        except Exception as exc:  # reject the file, keep going
            errors.append(f"{p.name}: {exc}")
    replaced = {c.document_id for c in new}
    merged = [c for c in load_chunks() if c.document_id not in replaced] + new
    save_chunks(merged)
    return new, errors


def delete_document(document_id: str) -> int:
    chunks = load_chunks()
    kept = [c for c in chunks if c.document_id != document_id]
    save_chunks(kept)
    return len(chunks) - len(kept)
