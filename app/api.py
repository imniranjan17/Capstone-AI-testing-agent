"""Step 9a: FastAPI service. Run: python -m uvicorn app.api:app --port 8100"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, model_validator

from app import observability as obs
from app import store
from app.graph import build_graph, run_pipeline
from app.rag.answer import ask as rag_ask
from app.rag.docs import domain_stats, list_domains
from app.rag.retriever import HybridRetriever

app = FastAPI(title="Web Testing Agent")
_graph = None   # lazily built; tests may replace
_retriever: HybridRetriever | None = None   # singleton so dense embeddings stay cached


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


class RunRequest(BaseModel):
    key: str = ""
    html: str | None = None
    url: str | None = None
    force: bool = False

    @model_validator(mode="after")
    def _one_input(self):
        if bool(self.html) == bool(self.url):
            raise ValueError("provide exactly one of html or url")
        if self.url and not self.url.lower().startswith(("http://", "https://")):
            raise ValueError("url must be http(s)")
        if self.html and not self.key:
            self.key = "pasted-dom"
        return self


class ReviewRequest(BaseModel):
    idx: int
    status: Literal["approved", "rejected"]
    note: str = ""
    final_fix: str | None = None


@app.post("/runs")
def create_run(req: RunRequest) -> dict:
    # sync def -> FastAPI runs it in a worker thread (the pipeline uses asyncio internally)
    try:
        return run_pipeline(req.key, req.html, req.url, req.force, graph=get_graph())
    except httpx.HTTPError as e:
        raise HTTPException(502, f"could not fetch url: {e.__class__.__name__}")


@app.get("/runs")
def runs(key: str | None = None, limit: int = 50) -> list[dict]:
    return store.list_runs(key, limit)


@app.get("/runs/{run_id}")
def read_run(run_id: str) -> dict:
    r = store.get_run(run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    return r


@app.get("/reviews/pending")
def pending(run_id: str | None = None) -> list[dict]:
    return store.pending_reviews(run_id)


@app.post("/runs/{run_id}/review")
def review(run_id: str, req: ReviewRequest) -> dict:
    try:
        return store.review(run_id, req.idx, req.status, req.note, req.final_fix)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


class AskRequest(BaseModel):
    question: str
    domain: str | None = None
    top_k: int = 8


@app.get("/audit/overview")
def audit_overview() -> dict:
    return obs.overview()


@app.get("/audit/contracts")
def audit_contracts() -> dict:
    return obs.CONTRACTS


@app.get("/audit/traces/{run_id}")
def audit_trace(run_id: str) -> dict:
    t = obs.trace_detail(run_id)
    if t is None:
        raise HTTPException(404, "trace not found")
    return t


@app.get("/domains")
def domains() -> list[dict]:
    return [{"domain": d, **{k: v for k, v in domain_stats(None, d).items() if k != "domain"}}
            for d in list_domains()]


@app.get("/stats")
def stats(domain: str | None = None) -> dict:
    return domain_stats(None, domain)


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    global _retriever
    if not req.question.strip():
        raise HTTPException(422, "question is empty")
    _retriever = _retriever or HybridRetriever()
    return rag_ask(req.question, req.domain, _retriever, min(max(req.top_k, 1), 20))


# Default UI: the React build (frontend/dist), served last so every API route above wins.
# If it hasn't been built, nothing is mounted and the Streamlit UI (ui/) remains the fallback.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="ui")
