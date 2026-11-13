# Web Testing Agent (demo)

Paste a page's DOM (or enter a URL). If it changed since the last snapshot, the agent runs accessibility, form validation, broken-link, security and MCP automation checks in parallel, then decides per finding: **auto-suggest a patch** (low-risk guideline) or **send to a human review queue**. It only suggests fixes; it never edits source.

See [CLAUDE.md](CLAUDE.md) for the workflow diagram and architecture.

## Setup
```
python -m pip install -e ".[dev]"
cp .env.example .env        # optional: set GROQ_API_KEY for LLM-drafted patch snippets
python -m pytest -q
```

## Demo (no UI)
```
python scripts/demo.py
```
Runs `demo/page_v1.html` (baseline) -> same again (unchanged, no checks) -> `demo/page_v2.html` (changed, defects) -> findings, decisions, one human approval.

## Demo (UI)
```
python -m uvicorn app.api:app --port 8100
python -m streamlit run ui/streamlit_app.py
```
Optional, for real WCAG findings: in `a11y_service/` run `python scripts/ingest_knowledge.py --no-dense` once, then `python -m uvicorn app.main:app --port 8000`. Without it the a11y branch reports `a11y-service-unavailable` and everything else still works.

### Testing the demo pages by URL
The agent only accepts `http(s)://` URLs, so `file:///...` paths are rejected. Serve the `demo/` folder over HTTP instead:
```
cd demo
python -m http.server 8200 --bind 127.0.0.1
```
Leave it running (its own terminal), then in the UI choose **URL** and enter one of:
- http://127.0.0.1:8200/product_page.html
- http://127.0.0.1:8200/page_v1.html (baseline), then http://127.0.0.1:8200/page_v2.html (changed)
- http://127.0.0.1:8200/test_page.html

Open the same URL in a browser to view the page. To re-run an unchanged page, tick force (or delete `data/testing_agent.db` for a fresh start). Stop the server with Ctrl+C.

Suggested live walkthrough: Run page -> paste `demo/page_v1.html` -> Run (baseline) -> Run again (unchanged) -> paste `demo/page_v2.html` -> Run (diff + findings) -> Review queue -> approve/reject.

## Customising decisions
Edit `guidelines/fixes.yaml`. A finding is auto-suggested only if its rule has a guideline with `auto_suggest: true`, `risk: low`, severity <= `max_severity`, is not a security finding, and has no failed MCP test on the same element. Everything else goes to a human.

## Limitations
- Static analysis only (no JS execution). Missing React `key` warnings need a browser console capture (future Playwright branch).
- MCP test cases are static HTML checks; swap the tool bodies in `mcp_server/server.py` for Playwright to make them real browser tests.
- Only test sites you are authorized to test.
