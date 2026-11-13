# Error Handling Checklist

## Branches (`app/branches/*`)
- [ ] Every branch returns `list[Finding]` and never raises (top-level try/except).
- [ ] Failure is surfaced as a low-severity finding (e.g. `a11y-service-unavailable`), not an empty list that looks like "all clear".
- [ ] External calls (HTTP, MCP stdio, LLM) have timeouts and bounded retries.
- [ ] Exceptions are caught specifically where possible; no bare `except:` that hides programming errors.

## Intake
- [ ] Empty, oversized, malformed, or non-HTML input is rejected with a clear 4xx, not a 500.
- [ ] URL fetching handles redirects, non-200, timeouts, and non-text content types; scheme is restricted (http/https only).
- [ ] SSRF considered: private/loopback/link-local targets blocked or explicitly allowed by config.
- [ ] Parser failures on broken HTML degrade gracefully.

## Pipeline / policy
- [ ] A failed branch does not abort the parallel fan-out; merge handles partial results.
- [ ] Failures that mean "could not verify" route to human review rather than auto-fix.
- [ ] LLM failure falls back to no patch text; the decision is unaffected (LLM never decides).
- [ ] Store/SQLite errors (locked, missing table) are handled and reported.

## API / UI
- [ ] Error responses do not leak stack traces or file paths.
- [ ] UI shows backend-down state instead of crashing.
