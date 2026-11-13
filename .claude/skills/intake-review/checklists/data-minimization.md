# Data Minimization Checklist

- [ ] Only the fields needed for diffing/checks are stored; no raw cookies, auth headers, or tokens from fetched pages.
- [ ] Snapshots store normalized DOM + hash; raw HTML retention is justified and bounded (size cap, retention period).
- [ ] Form values, `input[type=password]`, emails, and other PII in pasted DOM are stripped or redacted before storage.
- [ ] Fetched URLs have credentials and sensitive query params (`token`, `key`, `session`) removed before being stored or logged.
- [ ] `Finding` evidence is a short excerpt (selector/snippet), not the whole page.
- [ ] Logs and error messages do not include full page content or secrets.
- [ ] LLM patch prompts send only the finding + matching guideline, not the full page; no secrets in prompts.
- [ ] RAG docs index only finding fields needed for Q&A; nothing beyond the latest run per page is retained in memory.
- [ ] Data sent to external services (bundled a11y_service API, LLM provider) is limited to what the call requires.
- [ ] Old runs/snapshots have a documented deletion or pruning path.
- [ ] `.env` and DB files are git-ignored; no secrets in fixtures or tests.
