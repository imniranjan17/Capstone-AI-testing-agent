# WCAG-Grounded Accessibility Review Agent (prototype)

Paste HTML or upload an axe/generic report and get evidence-grounded verdicts against WCAG 2.2 AA.
Deterministic checks establish facts; hybrid retrieval (BM25 + dense -> RRF -> cross-encoder) fetches WCAG evidence; an LLM (Groq by default) only explains and recommends. **Verdicts are decided by code, not the LLM.** Results never claim whole-page or site conformance.

## Quick start (local demo)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # Linux/macOS: .venv/bin/python
cp .env.example .env                                  # then set GROQ_API_KEY=...
```

1. **Ingest the knowledge base** (local files only; no scraping):
   ```bash
   python scripts/ingest_knowledge.py            # chunks + BM25 + dense index (downloads bge-small on first run, ~130 MB)
   python scripts/ingest_knowledge.py --no-dense # BM25 only, no model downloads
   ```
2. **Run the API**: `python -m uvicorn app.main:app --port 8000`
3. **Run the UI**: `python -m streamlit run ui/streamlit_app.py` (opens http://localhost:8501)

> Disk-light mode: set `RETRIEVAL_ENABLED=false` in `.env` to skip PyTorch models entirely (BM25 + RRF only).
> Install sentence-transformers separately when you have ~3 GB free: `pip install sentence-transformers`.

## Analyze via curl

```bash
curl -s localhost:8000/v1/analyze -H 'content-type: application/json' -d '{
  "input_type":"html","target_standard":"WCAG_2_2_AA",
  "content":"<html><body><main><img src=\"a.png\"><button><svg aria-hidden=\"true\"></svg></button></main></body></html>"}'
```

Other inputs: `"input_type":"axe_report"` (axe `violations`/`incomplete`/`passes`) or `"report"` (`findings[]` with `rule`, `element`, `message`). Add `?debug=true` for retrieval rankings.

| Endpoint | Purpose |
|---|---|
| `POST /v1/analyze` | Analyze HTML / axe report / generic report |
| `GET /v1/runs/{id}?format=json\|html` | Stored result |
| `POST /v1/knowledge/ingest` | Ingest from a directory inside `knowledge/` |
| `DELETE /v1/knowledge/documents/{document_id}` | Remove a document from all indexes |
| `GET /health` | API, vector DB, model, browser readiness |

## Tests
```bash
python -m pytest -q      # unit + integration + golden; offline, no API key, no model downloads
```

## Docker
```bash
docker compose up --build    # api :8000, qdrant :6333, ui :8501
docker compose exec api python scripts/ingest_knowledge.py
```

## Configuration
See `.env.example`. LLM = any OpenAI-compatible endpoint (`LLM_BASE_URL`, `LLM_MODEL`, `GROQ_API_KEY`). Embedding and reranker model IDs are configurable.

## Verdicts
`FAIL` needs an observed failure + retrieved normative WCAG evidence. `PASS` applies only to the executed rule. Anything needing visual/interaction/human judgment is `MANUAL_REVIEW`. Unsupported claims are `INSUFFICIENT_EVIDENCE`. Overall: FAIL > MANUAL_REVIEW > INSUFFICIENT_EVIDENCE > `PASS_WITH_SCOPE_LIMITATION`.

## Known limitations
- The bundled WCAG data is a **paraphrased** subset of Level A/AA criteria, not W3C's verbatim text. Replace/extend with official text via the ingest command (JSON, or Markdown/HTML/text plus a `<file>.meta.json` provenance sidecar).
- Not yet built: Playwright/axe URL mode, retrieval benchmark runner and the full 60-case dataset (a 35-case golden smoke set is included).
- Static analysis cannot judge focus order/visibility, target size, alt-text quality or decorative intent; these surface as `MANUAL_REVIEW`.
