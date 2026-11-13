import json

import pytest

from app.knowledge.chunker import chunk_file, chunk_normative_json
from app.knowledge.schemas import Chunk, RetrievalFilter
from app.retrieval.bm25_index import BM25Index
from app.retrieval.reranker import rerank
from app.retrieval.rrf import rrf_fuse


def test_rrf_fusion_and_provenance():
    out = rrf_fuse([("a", 9.0), ("b", 5.0)], [("b", 0.9), ("c", 0.5)], k=60)
    ids = [o["chunk_id"] for o in out]
    assert ids[0] == "b"  # appears in both lists
    b = out[0]
    assert b["sparse_rank"] == 2 and b["dense_rank"] == 1
    assert b["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)
    assert len(ids) == len(set(ids))


def test_chunker_one_chunk_per_criterion(retriever):
    normative = [c for c in retriever.chunks if c.authority == "normative"]
    scs = [c.success_criterion for c in normative]
    assert len(scs) == len(set(scs)) and "4.1.2" in scs
    assert all(c.level in ("A", "AA") and c.source_url and c.checksum for c in retriever.chunks)


def test_explanatory_chunks_link_to_parent(retriever):
    expl = [c for c in retriever.chunks if c.authority == "official_explanatory"]
    assert expl and all(c.success_criterion and c.level for c in expl)


def test_chunk_without_provenance_rejected():
    with pytest.raises(ValueError):
        Chunk(chunk_id="x", document_id="d", document="", document_version="2.2", authority="normative",
              success_criterion="1.1.1", content="text", source_url="", retrieved="2026", checksum="c")


def test_text_file_requires_sidecar(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("hello")
    with pytest.raises(ValueError, match="provenance"):
        chunk_file(p)


def test_bm25_finds_exact_ids_and_filters_levels(retriever):
    idx = BM25Index(retriever.chunks)
    flt = RetrievalFilter()
    res = idx.search("button-name accessible name aria-label button", flt)
    assert res and retriever.by_id[res[0][0]].success_criterion == "4.1.2"
    top = [retriever.by_id[c] for c, _ in idx.search("language of page lang html-has-lang", flt)]
    assert top[0].success_criterion == "3.1.1"
    only_aa = idx.search("contrast", RetrievalFilter(levels=["AA"]))
    assert all(retriever.by_id[c].level == "AA" for c, _ in only_aa)


def test_normative_preferred_on_near_tie(retriever):
    norm = next(c for c in retriever.chunks if c.authority == "normative")
    expl = next(c for c in retriever.chunks if c.authority == "official_explanatory")

    class Tie:
        def score(self, pairs):
            return [1.0 for _ in pairs]

    ranked = rerank("q", [expl, norm], Tie(), top_k=2)
    assert ranked[0][0].authority == "normative"


def test_aaa_never_retrieved(retriever):
    assert not any(c.level == "AAA" for c in retriever.chunks)
