# CLAUDE.md

WCAG-grounded accessibility review agent (prototype, WCAG 2.2 AA). Accepts HTML, an axe-core report, or a generic report and returns `PASS` / `FAIL` / `MANUAL_REVIEW` / `INSUFFICIENT_EVIDENCE` per finding, with an overall verdict that never claims page/site conformance.

## Commands (Windows: use `.venv/Scripts/python`; elsewhere `.venv/bin/python`)
- Install: `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"`
- Test everything: `python -m pytest -q` (no model downloads, no network, no API key needed)
- Ingest knowledge: `python scripts/ingest_knowledge.py` (add `--no-dense` for BM25-only)
- Rebuild dense index only: `python scripts/build_indexes.py`
- API: `python -m uvicorn app.main:app --port 8000` · UI: `python -m streamlit run ui/streamlit_app.py`

## Architecture (data flow)
`app/agent/graph.py` is a linear LangGraph of 13 nodes (all in `app/agent/nodes/pipeline.py`, bound to a retriever and optional LLM via `make_nodes`):
validate -> parse -> deterministic checks (`app/analysis/dom_checks.py`) -> normalize into `Observation`s -> query builder -> BM25 -> dense -> RRF -> cross-encoder -> evaluate (LLM explanation) -> **verdict policy** -> report -> persist (SQLite).

Only `status == "fail"` observations go through retrieval. Manual/pass observations look up their mapped criteria locally via `Retriever.lookup`.

## Invariants — do not break these
- **Verdicts come from `app/evaluation/policy.py`, never from the LLM.** The LLM (`evaluator.py`) only supplies `reason`, `recommendation`, and criterion IDs; IDs not present in the retrieved evidence are dropped (zero fabricated criteria).
- A `FAIL` needs a deterministic/report observation AND retrieved *normative* chunk whose SC is in the observation's `candidate_criteria` (from `knowledge/mappings/axe_rules.json` + axe `wcagXYZ` tags). Otherwise `INSUFFICIENT_EVIDENCE`.
- `PASS` is rule-scoped. Overall pass is `PASS_WITH_SCOPE_LIMITATION`, and the scope statement (`SCOPE_LIMITATION` in `app/schemas.py`) must always be in the report.
- Things statically undecidable (focus order/visibility, target size, alt-text quality, decorative-image intent) emit `manual` observations, never PASS.
- Static mode never executes JS. HTML shown in reports is escaped; sensitive input values are redacted in `html_parser.excerpt`.
- Retrieval debug is only returned when `?debug=true` and is never read back from storage.
- No web scraping at analysis time. Knowledge enters only via the ingest command from local files; every chunk requires provenance (`Chunk` validators).
- Level filter is A + AA only (no AAA) for the WCAG 2.2 AA target.

## Graceful degradation
- No `GROQ_API_KEY` -> no explanations, deterministic results still returned (warning added).
- Dense/reranker unavailable (or `RETRIEVAL_ENABLED=false`) -> BM25 (+RRF) only; stage status in `Retriever.status`.
- Empty knowledge base -> fails become `INSUFFICIENT_EVIDENCE`.

## Config
All in `app/config.py` / `.env` (see `.env.example`). LLM is any OpenAI-compatible endpoint; defaults target **Groq** (`https://api.groq.com/openai/v1`, `llama-3.3-70b-versatile`). Groq has no embeddings API, so the bi-encoder and cross-encoder run locally with sentence-transformers (lazy-imported). Qdrant uses embedded local mode unless `QDRANT_URL` is set.

## Testing notes
- `tests/conftest.py` forces BM25-only, a temp SQLite DB, and no LLM key. `FakeLLM` there simulates the chat client.
- `tests/golden/cases.json` is a 35-case smoke set (not the full 60-case benchmark of the spec).
- To add a check: write it in `dom_checks.py`, register in `CHECKS`, map its rule ID in `axe_rules.json`, add unit + golden cases.

## Known limitations
- `knowledge/normative/wcag22_a_aa.json` holds **paraphrased** criterion summaries (covers a subset of A/AA criteria), not verbatim W3C text. Replace via the ingest command before quoting.
- Not implemented yet: Playwright/axe URL mode (`/v1/analyze-url`), retrieval benchmark/metrics runner (`scripts/run_evaluation.py`), techniques ingestion examples.
- Contrast is only checked when elements carry `data-computed-color` / `data-computed-bg`.
