---
name: intake-review
description: Review code that ingests external input (pasted DOM/HTML, URLs, API payloads, stored snapshots) against modular checklists for data minimization, error handling, auditability, and test coverage. Use when reviewing intake paths, branches, store/snapshot changes, or API endpoints.
---

# Intake Review

Review how data enters, is processed by, and is persisted in this agent. Each dimension has its own checklist; load only what the change touches.

## Checklists

| Dimension | File | Load when the change touches... |
|---|---|---|
| Data minimization | [checklists/data-minimization.md](checklists/data-minimization.md) | snapshot storage, findings, logs, RAG docs, LLM prompts |
| Error handling | [checklists/error-handling.md](checklists/error-handling.md) | branches, fetchers, MCP, LLM calls, API handlers |
| Auditability | [checklists/auditability.md](checklists/auditability.md) | policy/decide, review queue, run history, patches |
| Test coverage | [checklists/test-coverage.md](checklists/test-coverage.md) | any code change |

## Procedure

1. Identify changed files (or the target the user named) and map each to the dimensions above.
2. Read only the relevant checklist files; walk each item and mark Pass / Fail / N/A with `file:line` evidence.
3. Check project invariants in [CLAUDE.md](../../../CLAUDE.md) (suggest-only fixes, deterministic decisions, branches never raise, untrusted finding text).
4. Report using the format below. Do not edit code unless asked.

## Report format

```
## Intake review: <target>
Scope: <files> | Dimensions: <list>

### Findings (most severe first)
- [High|Med|Low] <dimension> — <file:line> — <issue> — <suggested fix>

### Checklist summary
| Dimension | Pass | Fail | N/A |

### Verdict: approve | approve with follow-ups | changes required
```

Severity: High = leaks data, silently swallows failures that skip human review, or breaks an invariant; Med = missing audit trail or untested branch; Low = hygiene.
