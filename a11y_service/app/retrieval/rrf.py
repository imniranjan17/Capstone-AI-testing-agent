"""Reciprocal Rank Fusion with per-document provenance."""
from __future__ import annotations

from typing import Any


def rrf_fuse(
    sparse: list[tuple[str, float]], dense: list[tuple[str, float]], k: int = 60, top_n: int = 20,
) -> list[dict[str, Any]]:
    """Inputs are ranked (chunk_id, score) lists, best first. Output deduplicated by chunk_id."""
    fused: dict[str, dict[str, Any]] = {}
    for name, ranked in (("sparse", sparse), ("dense", dense)):
        for rank, (cid, score) in enumerate(ranked, start=1):
            entry = fused.setdefault(cid, {
                "chunk_id": cid, "sparse_rank": None, "dense_rank": None,
                "sparse_score": None, "dense_score": None, "rrf_score": 0.0,
            })
            entry[f"{name}_rank"] = rank
            entry[f"{name}_score"] = score
            entry["rrf_score"] += 1.0 / (k + rank)
    return sorted(fused.values(), key=lambda e: (-e["rrf_score"], e["chunk_id"]))[:top_n]
