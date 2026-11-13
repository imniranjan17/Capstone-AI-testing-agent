# Demo Guide — Web Testing Agent

A talk track for presenting the agent. Pair it with [README.md](README.md) (setup) and [CLAUDE.md](CLAUDE.md) (architecture).

## 1. One-line pitch
Give it a page (pasted DOM or a URL). If the page changed since last time, it checks accessibility, forms, links, security and automated test cases **in parallel**, then decides for each issue: **suggest a safe patch automatically** or **ask a human**. It never edits your code.

## 2. Before you start
```
# terminal 1 – API
python -m uvicorn app.api:app --port 8100
# terminal 2 – UI
python -m streamlit run ui/streamlit_app.py
# terminal 3 – demo page server
cd demo && python -m http.server 8200 --bind 127.0.0.1
# terminal 4 (optional, real WCAG findings) – from the a11y_service folder (run ingest_knowledge.py once first)
python -m uvicorn app.main:app --port 8000
```
Demo URL: **http://127.0.0.1:8200/product_page.html**
Fresh start: delete `data/testing_agent.db`.

## 3. How it works (what to say)
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
It is a **pipeline** (LangGraph), not a main agent with sub-agents. Each box is a plain function over shared state, so results are predictable and testable. The five checks run at the same time; merge waits for all of them.

### Step by step when a URL is entered
1. **Fetch** – the API downloads the page and keeps the HTML and response headers.
2. **Snapshot/diff** – scripts, comments and tokens are stripped, the page is hashed and compared with the last stored version for that URL.
   - first time = `baseline` (everything runs) · same hash = `unchanged` (stop, nothing runs) · different = `changed` (run + show diff)
3. **Five parallel checks**

   | Check | Looks for |
   |---|---|
   | a11y | WCAG issues (calls the bundled `a11y_service` accessibility agent) |
   | validation | form problems: no submit button, wrong input types, weak password fields |
   | links | broken (404/timeouts) and placeholder `#` links |
   | security | missing headers (CSP, HSTS…), inline handlers, `target=_blank` without `noopener`, password form over GET |
   | mcp_tests | automation test cases served by an MCP server (form submit, nav links, page basics) |
4. **Merge** – removes duplicates.
5. **Decide** – deterministic rules (below). The LLM never decides.
6. **Report + save** – counts, diff, findings stored in SQLite; items needing a human are queued.

### Decision rules (in order, first match wins)
A finding goes to a **human** if: it is a security issue · it is a failed MCP test · no guideline matches · the guideline says human-only or is not low-risk · severity is above the guideline limit · an MCP test failed on the same element. Otherwise it is **auto-suggested** with the guideline's fix text (optionally LLM-drafted snippet).
Guidelines live in `guidelines/fixes.yaml` — edit them live to change behaviour.

## 4. Live demo script (about 5 minutes)

| # | Action | What to say |
|---|---|---|
| 1 | **Run** page → URL → paste the demo URL → Run | "First visit, so it's a *baseline*. All five checks ran in parallel." |
| 2 | Show metrics + Findings table; filter by category | "15 issues. Broken links, missing `lang`, missing security headers, placeholder link." |
| 3 | **Suggested patches** tab | "Low-risk, guideline-backed fixes are suggested automatically — here, email field should use `type=email`." |
| 4 | Click Run again | "Same page → *unchanged*. No checks run, no wasted work." |
| 5 | Edit `demo/product_page.html` (e.g. add `lang="en"`, fix the Pricing link) → Run | "DOM changed → checks re-run, and the **DOM diff** tab shows exactly what changed." |
| 6 | **Review queue** | "Anything risky — security, broken links, failed tests — waits here with the reason it needs a human." |
| 7 | Edit a suggested fix, add a note, **Approve** one and **Reject** one | "Human decisions are recorded; each item can only be reviewed once." |
| 8 | **History** | "Every run is kept so you can reopen or compare." |
| 9 | (Optional) paste raw HTML instead of a URL | "Works for pasted DOM too — useful for pages behind login." |

### Ask (RAG) — multi-page questions (extra 2 minutes)
Test several pages of one site (paste each URL on **Run**: e.g. `product_page.html` and `test_page.html`). Open **Ask (RAG)**, pick the domain, ask: "Which pages have dead links?", "What critical security issues exist?", "How many findings per page?".
Say: findings of each page's *latest* run are indexed per domain. Retrieval is **hybrid**: BM25 (exact words like `noopener`, rule IDs) + dense embeddings (meaning, e.g. "dead links" ~ "404") fused with **RRF**. The Sources table shows each hit's BM25 rank, dense rank and fused score. Counts/totals are computed exactly, not guessed by the model. Without a `GROQ_API_KEY` it shows the matching findings instead of a written answer.

## 5. Mistakes planted in `demo/product_page.html`
No `lang` on `<html>` · hero image missing alt (and file 404s) · Pricing link is `#` · Privacy and Twitter links return 404 · Twitter link `target=_blank` without `noopener` · email field is `type=text` · form uses GET · no security headers (simple dev server).
Other pages: `demo/page_v1.html` (clean) vs `demo/page_v2.html` (defects) for the baseline → changed story; `python scripts/demo.py` runs that story in the terminal.

## 6. Likely questions
- **Does the AI decide?** No. Decisions are rule-based and auditable; the LLM only drafts patch text, and only if an API key is set.
- **Does it fix my code?** No — suggest-only, by design.
- **Why is almost everything "needs human"?** Security, test failures and judgement calls (where should a broken link point?) are deliberately not automated. Only low-risk, mechanical fixes auto-suggest.
- **Why no a11y findings on screen?** the a11y_service isn't running. Start it on port 8000 for WCAG results; otherwise that check shows "service unavailable" and the rest still works.
- **What if one check crashes?** It becomes a finding; the other checks still finish.
- **Can it test JS-rendered / React apps?** Not yet — static HTML only. Next step is a Playwright branch (captures console warnings like React's missing `key`, runs real browser flows).
- **Is it safe to point at any site?** Only test sites you're authorized to. Add a domain allow-list before exposing the API.

## 7. Known limitations (be upfront)
Static analysis only · MCP test cases are HTML checks, not browser flows · security checks are basic hygiene, not a penetration test · header checks need URL mode (pasted HTML has no headers) · a11y depends on the separate RAG-Handson service.
