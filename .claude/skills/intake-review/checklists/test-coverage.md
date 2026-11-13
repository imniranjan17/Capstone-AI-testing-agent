# Test Coverage Checklist

Run: `python -m pytest -q`

## Per change
- [ ] New or changed behavior has a test; bug fixes have a regression test that fails without the fix.
- [ ] Both happy path and failure path are covered.

## Snapshot / diff
- [ ] baseline, changed, and unchanged outcomes each tested; unchanged short-circuits to END.
- [ ] Normalization: whitespace/attribute-order noise yields the same hash; real changes do not.

## Branches
- [ ] Each branch tested with a positive fixture (finding raised) and a clean fixture (none).
- [ ] "Never raises" tested with malformed input and a simulated dependency failure (a11y API down, MCP error).
- [ ] No tests require live network, RAG-Handson, or an LLM key; these are mocked.

## Policy / decide
- [ ] Each human-review invariant has a test: security, auth, high severity, no matching guideline, failed MCP test.
- [ ] Guideline-matched low-risk finding yields an auto-suggest.
- [ ] Decisions are unchanged when LLM patching is disabled or fails.

## API / store / RAG
- [ ] API endpoints tested for valid input, invalid input, and error responses.
- [ ] Review queue lifecycle (enqueue, resolve) tested using a temp DB, not the real one.
- [ ] RAG: domain filter applied before ranking, counts come from `domain_stats`, extractive fallback works with no LLM.
- [ ] Prompt-injection text in finding content does not alter RAG answer behavior.

## Hygiene
- [ ] Tests are deterministic and isolated (temp dirs, no shared state, no order dependence).
- [ ] Fixtures contain no real PII or secrets.
