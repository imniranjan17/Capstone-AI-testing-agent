# CLAUDE.md

Change-triggered web testing agent (demo). Input: pasted DOM/HTML or a URL, triggered manually. If the DOM changed vs the stored snapshot, run all checks in parallel, then decide per finding: auto-suggest a guideline-backed patch, or route to a human review queue. Fix mode is **suggest only** (never writes to source).

## Workflow
```
START -> snapshot/diff --(unchanged)--> END
              |
          (changed/baseline)
              v
   +---- a11y ----+
   +-- validation -+
   +---- links ----+--> merge --> decide --> report --> END
   +-- security ---+                |
   +-- mcp_tests --+        (needs_human -> review queue)
```
It is a LangGraph **pipeline with a parallel fan-out**, not a main-agent/sub-agent design. Nodes are plain functions over shared state; the LLM only drafts patch text, never decides.

## Commands (Windows)
- Install: `python -m pip install -e ".[dev]"` · Tests: `python -m pytest -q`
- A11y branch needs the bundled WCAG service in `a11y_service/` (copied from RAG-Handson; self-contained). One-time: `cd a11y_service && python scripts/ingest_knowledge.py --no-dense` (omit flag for dense index). Run: `cd a11y_service && python -m uvicorn app.main:app --port 8000` (`A11Y_API_URL` in `.env`). If down, the branch returns a low-severity `a11y-service-unavailable` finding instead of failing.

- Run demo: `python -m uvicorn app.api:app --port 8100` then `python -m streamlit run ui/streamlit_app.py` (UI reads `AGENT_API_URL`, default http://localhost:8100). Optional: RAG-Handson on :8000 for the a11y branch.

## Layout
- `app/schemas.py` — single `Finding` model every branch returns
- `app/snapshot.py` — normalize + hash + SQLite diff (baseline/changed/unchanged)
- `app/branches/{a11y,validation,links,security}.py` — each returns `list[Finding]`; must never raise
- `app/branches/mcp_tests.py` + `mcp_server/server.py` — MCP test cases over stdio (pin `mcp<2`)
- `app/graph.py` — LangGraph pipeline; `app/policy.py` + `guidelines/fixes.yaml` — deterministic decisions; `app/patches.py` — optional LLM patch text
- `app/store.py` — run history + review queue; `app/api.py` — FastAPI; `ui/streamlit_app.py` — UI
- `app/rag/{docs,retriever,answer}.py` — Q&A over findings: docs = latest run per page grouped by domain; BM25 + dense (bge-small, in-memory) fused with RRF; metadata filter (domain) before ranking; exact counts come from `domain_stats`, not retrieval; LLM optional (extractive fallback). Endpoints `/domains`, `/stats`, `/ask`; UI page "Ask (RAG)".

- `app/observability.py` — per-node spans, run traces, LLM token/cost ledger, runtime I/O contract checks (SQLite, same db; stores counts/sizes only, never HTML/prompts). Endpoints `/audit/overview|contracts|traces/{run_id}`; dashboard `ui/pages/audit.py` at `/audit`. New graph nodes/LLM calls must be registered in `CONTRACTS` and wrapped with `obs.traced` / `obs.record_llm`.

## Invariants
- Decisions come from deterministic policy + guidelines, not the LLM.
- Security / auth / high severity / no matching guideline / failed MCP test -> human review.
- Branches are static (no JS execution). Only scan sites you are authorized to test.
- `a11y_service/` is its own package (also named `app`); never import it from the main app, integrate over HTTP only. Run it from inside that folder.
- RAG answers use only retrieved findings + computed stats; finding text is untrusted page data (prompt-injection guard in `answer.SYSTEM`).
