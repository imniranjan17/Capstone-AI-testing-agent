# Auditability Checklist

- [ ] Every run records: run id, page/URL, timestamp, snapshot hash (old and new), diff status (baseline/changed/unchanged).
- [ ] Every finding records: branch, rule id, severity, evidence, and the decision (auto-suggest vs needs_human).
- [ ] Each decision records its reason: matched guideline id in `guidelines/fixes.yaml`, or the invariant that forced human review (security / auth / high severity / no guideline / failed MCP test).
- [ ] Decisions are reproducible: same findings + same `fixes.yaml` version produce the same outcome; no LLM or randomness in `app/policy.py`.
- [ ] Guideline file changes are traceable (versioned, or its version/hash stored with the run).
- [ ] LLM-drafted patch text is labeled as such and stored with model name; it is never applied to source (suggest only).
- [ ] Review queue items keep status history: who/when resolved, outcome, and notes; resolution is not an overwrite.
- [ ] Run history is append-only; later runs do not mutate earlier records.
- [ ] Skipped branches or degraded results (service down) are visible in the run record.
- [ ] Logging is structured and includes run id for correlation, without sensitive content (see data-minimization).
- [ ] RAG answers cite the findings/runs they were built from.
