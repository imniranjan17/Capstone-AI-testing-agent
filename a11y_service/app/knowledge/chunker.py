"""Criterion-aware chunking. One chunk per success criterion; explanatory text keeps its parent link."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.knowledge.schemas import Chunk

_WORDS_PER_CHUNK = 380  # ~ 500 tokens
_WORD_OVERLAP = 45  # ~ 60 tokens


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _window(text: str) -> list[str]:
    """Split long explanatory text into overlapping windows; short text stays intact."""
    words = text.split()
    if len(words) <= _WORDS_PER_CHUNK:
        return [text.strip()]
    out, start = [], 0
    while start < len(words):
        out.append(" ".join(words[start:start + _WORDS_PER_CHUNK]))
        if start + _WORDS_PER_CHUNK >= len(words):
            break
        start += _WORDS_PER_CHUNK - _WORD_OVERLAP
    return out


def _strip_html(raw: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    return " ".join(soup.get_text(" ").split())


def _level_lookup(criteria: list[dict]) -> dict[str, tuple[str, str, str, str]]:
    return {c["sc"]: (c["level"], c.get("principle", ""), c.get("guideline", ""), c["title"]) for c in criteria}


def chunk_normative_json(data: dict) -> list[Chunk]:
    doc_id = data["document_id"]
    chunks = []
    for c in data["criteria"]:
        body = c["content"]
        chunks.append(Chunk(
            chunk_id=f"{doc_id}-sc-{c['sc']}", document_id=doc_id, document=data["title"],
            document_version=data["version"], authority=data["authority"],
            principle=c.get("principle", ""), guideline=c.get("guideline", ""),
            success_criterion=c["sc"], title=c["title"], level=c["level"], section_type="criterion",
            content=body, source_url=c["url"], retrieved=data["retrieved"], checksum=checksum(body),
        ))
    return chunks


def chunk_sections_json(data: dict, criteria_ref: dict[str, tuple[str, str, str, str]]) -> list[Chunk]:
    doc_id = data["document_id"]
    chunks = []
    for i, s in enumerate(data["sections"]):
        sc = s["parent_sc"]
        level, principle, guideline, title = criteria_ref.get(sc, ("", "", "", ""))
        for j, piece in enumerate(_window(s["content"])):
            chunks.append(Chunk(
                chunk_id=f"{doc_id}-{sc}-{s.get('section_type', 'note')}-{i}-{j}", document_id=doc_id,
                document=data["title"], document_version=data["version"], authority=data["authority"],
                principle=principle, guideline=guideline, success_criterion=sc, title=title, level=level,
                section_type=s.get("section_type", "note"), content=piece, source_url=s["url"],
                retrieved=data["retrieved"], checksum=checksum(piece),
            ))
    return chunks


def chunk_text_file(path: Path, meta: dict, criteria_ref: dict[str, tuple[str, str, str, str]]) -> list[Chunk]:
    """Markdown/HTML/text with a sidecar `<file>.meta.json` supplying provenance."""
    raw = path.read_text(encoding="utf-8")
    text = _strip_html(raw) if path.suffix.lower() in (".html", ".htm") else raw
    sc = meta.get("parent_sc", "")
    level, principle, guideline, title = criteria_ref.get(sc, ("", "", "", meta.get("title", "")))
    chunks = []
    for j, piece in enumerate(_window(re.sub(r"\n{3,}", "\n\n", text))):
        chunks.append(Chunk(
            chunk_id=f"{meta['document_id']}-{j}", document_id=meta["document_id"], document=meta["title"],
            document_version=meta["version"], authority=meta["authority"], principle=principle,
            guideline=guideline, success_criterion=sc or "n/a", title=title, level=level,
            section_type=meta.get("section_type", "note"), content=piece, source_url=meta["source_url"],
            retrieved=meta["retrieved"], checksum=checksum(piece),
        ))
    return chunks


def chunk_file(path: Path, criteria_ref: dict[str, tuple[str, str, str, str]] | None = None) -> list[Chunk]:
    """Chunk a supported file. The mapping file (rules) is not retrievable text and yields no chunks."""
    criteria_ref = criteria_ref or {}
    suffix = path.suffix.lower()
    if suffix == ".json":
        if path.name.endswith(".meta.json"):
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if "criteria" in data:
            return chunk_normative_json(data)
        if "sections" in data:
            return chunk_sections_json(data, criteria_ref)
        return []
    if suffix in (".md", ".txt", ".html", ".htm"):
        meta_path = path.with_name(path.name + ".meta.json")
        if not meta_path.exists():
            raise ValueError(f"{path.name}: missing provenance sidecar {meta_path.name}")
        return chunk_text_file(path, json.loads(meta_path.read_text(encoding="utf-8")), criteria_ref)
    raise ValueError(f"Unsupported file type: {path.name}")


def build_criteria_ref(paths: list[Path]) -> dict[str, tuple[str, str, str, str]]:
    ref: dict[str, tuple[str, str, str, str]] = {}
    for p in paths:
        if p.suffix.lower() == ".json" and not p.name.endswith(".meta.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            if "criteria" in data:
                ref.update(_level_lookup(data["criteria"]))
    return ref
