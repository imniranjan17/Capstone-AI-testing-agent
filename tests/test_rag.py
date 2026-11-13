import pytest
from fastapi.testclient import TestClient

from app import api
from app.config import settings
from app.graph import build_graph, run_pipeline
from app.policy import make_decider
from app.rag.answer import SYSTEM, ask
from app.rag.docs import build_docs, domain_of, domain_stats, list_domains
from app.rag.retriever import HybridRetriever, rrf_fuse
from app.schemas import Category, Finding, Severity


def F(rule, msg, cat=Category.links, sev=Severity.high):
    return Finding(source="x", category=cat, severity=sev, rule_id=rule, message=msg, selector="a")


class FakeEmbedder:
    """Bag-of-keywords embedder so dense retrieval is testable without model downloads."""
    VOCAB = ["broken", "link", "security", "header", "form", "password", "image", "alt"]

    def _v(self, t):
        t = t.lower()
        return [float(w in t) for w in self.VOCAB]

    def embed_docs(self, texts):
        return [self._v(t) for t in texts]

    def embed_query(self, t):
        return self._v(t)


@pytest.fixture
def db(tmp_path):
    db = str(tmp_path / "r.db")
    pages = {
        "https://my-product.com/": [F("broken-link", "https://my-product.com/x -> 404")],
        "https://my-product.com/pricing": [
            F("missing-header", "Missing security header: csp", Category.security, Severity.medium),
            F("password-in-get", "Form with password field uses GET", Category.security, Severity.critical)],
        "https://other.org/": [F("image-alt", "img lacks alt", Category.accessibility)],
    }
    for url, fs in pages.items():
        g = build_graph({"v": lambda s, fs=fs: fs}, decide=make_decider())
        run_pipeline(url, html=f"<p>{url}</p>", db_path=db, graph=g)
    return db


def test_rrf_fusion_and_provenance():
    r = rrf_fuse([("a", 3), ("b", 2)], [("b", .9), ("c", .8)])
    assert r[0]["doc_id"] == "b" and r[0]["sparse_rank"] == 2 and r[0]["dense_rank"] == 1
    assert {x["doc_id"] for x in r} == {"a", "b", "c"}


def test_domains_and_docs(db):
    assert domain_of("https://my-product.com/a") == "my-product.com" and domain_of("demo") == "pasted"
    assert list_domains(db) == ["my-product.com", "other.org"]
    docs = build_docs(db, "my-product.com")
    assert {d.meta["domain"] for d in docs} == {"my-product.com"}
    assert sum(d.meta["kind"] == "finding" for d in docs) == 3
    st = domain_stats(db, "my-product.com")
    assert st["page_count"] == 2 and st["total_findings"] == 3 and st["by_category"]["security"] == 2


def test_latest_run_per_page_only(db):
    g = build_graph({"v": lambda s: []}, decide=make_decider())
    run_pipeline("https://my-product.com/", html="<p>changed</p>", db_path=db, graph=g)   # page fixed
    assert domain_stats(db, "my-product.com")["total_findings"] == 2


def test_hybrid_search_filters_by_domain(db):
    r = HybridRetriever(embedder=FakeEmbedder(), use_dense=True, db_path=db)
    hits = r.search("broken link", "my-product.com", top_k=3)
    assert hits[0]["meta"]["rule_id"] == "broken-link"
    assert hits[0]["sparse_rank"] and hits[0]["dense_rank"]          # both retrievers contributed
    assert all(h["meta"]["domain"] == "my-product.com" for h in hits)
    assert r.status["dense"] == "ok"


def test_bm25_only_fallback(db):
    r = HybridRetriever(use_dense=False, db_path=db)
    hits = r.search("password GET form", "my-product.com")
    assert hits[0]["meta"]["rule_id"] == "password-in-get" and hits[0]["dense_rank"] is None


def test_dense_unavailable_degrades(db, monkeypatch):
    import app.rag.retriever as m

    def boom(name):
        raise OSError("offline")

    monkeypatch.setattr(m, "SentenceTransformerEmbedder", boom)
    r = HybridRetriever(use_dense=True, db_path=db)
    assert r.search("broken link", "my-product.com") and "unavailable" in r.status["dense"]


def test_ask_llm_and_extractive(db):
    r = HybridRetriever(use_dense=False, db_path=db)
    seen = {}

    def fake_llm(system, user):
        seen["u"] = user
        return "Two [1]"

    a = ask("how many security issues?", "my-product.com", r, db_path=db, llm=fake_llm)
    assert a["mode"] == "llm" and a["answer"] == "Two [1]" and '"security": 2' in seen["u"]
    assert "untrusted" in SYSTEM
    a = ask("broken link", "my-product.com", r, db_path=db, llm=lambda s, u: None)
    assert a["mode"] == "extractive" and a["sources"]
    assert ask("anything", "nope.com", r, db_path=db)["mode"] == "empty"


def test_api(db, monkeypatch):
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "dense_enabled", False)
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(api, "_retriever", None)
    c = TestClient(api.app)
    assert {d["domain"] for d in c.get("/domains").json()} == {"my-product.com", "other.org"}
    assert c.get("/stats", params={"domain": "other.org"}).json()["total_findings"] == 1
    a = c.post("/ask", json={"question": "broken link", "domain": "my-product.com"}).json()
    assert a["sources"] and a["stats"]["domain"] == "my-product.com"
    assert c.post("/ask", json={"question": "  "}).status_code == 422
