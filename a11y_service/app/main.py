from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import routes_analysis, routes_knowledge, routes_runs
from app.config import get_settings
from app.knowledge.loader import load_chunks
from app.retrieval import service

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("app.request")

app = FastAPI(title="WCAG Accessibility Review Agent", version="0.1.0")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    limit = get_settings().max_payload_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        return JSONResponse({"detail": f"Payload exceeds {limit} bytes"}, status_code=413,
                            headers={"x-request-id": request_id})
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    log.info(json.dumps({"request_id": request_id, "method": request.method, "path": request.url.path,
                         "status": response.status_code, "ms": round((time.perf_counter() - start) * 1000, 1)}))
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    # Don't echo submitted content (it may contain sensitive data).
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    retriever = service._instance
    qdrant = "not_loaded"
    if retriever is not None:
        qdrant = "ready" if retriever.status["dense"] else "unavailable"
    return {
        "api": "ok",
        "knowledge_chunks": len(load_chunks()),
        "vector_db": {"mode": "server" if s.qdrant_url else "embedded", "status": qdrant},
        "models": {
            "embedding": s.embed_model, "reranker": s.rerank_model, "llm": s.llm_model,
            "llm_configured": bool(s.effective_llm_key),
            "loaded": None if retriever is None else {"dense": retriever.status["dense"],
                                                      "reranker": retriever.status["reranker"]},
        },
        "browser": "not_implemented",
    }


app.include_router(routes_analysis.router)
app.include_router(routes_knowledge.router)
app.include_router(routes_runs.router)
