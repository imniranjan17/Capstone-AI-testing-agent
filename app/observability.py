"""Pipeline observability: per-node spans, run traces, LLM token/cost ledger, and runtime I/O contract checks.

Design rules
- Never raises into the pipeline (observability must not break a run).
- Data minimization: stores sizes/counts/ids only, never page HTML, prompts or completions.
- Contracts are deterministic checks on node inputs/outputs; violations are recorded, not enforced.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from app.config import settings
from app.schemas import Decision, Finding

_ctx: ContextVar[tuple[str | None, str | None]] = ContextVar("obs_ctx", default=(None, None))  # (run_id, node)

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (run_id TEXT PRIMARY KEY, key TEXT, dom_status TEXT, duration_ms REAL,
    total_findings INTEGER, error TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS spans (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, node TEXT, kind TEXT,
    duration_ms REAL, status TEXT, input TEXT, output TEXT, contract_ok INTEGER, violations TEXT, error TEXT,
    created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS llm_calls (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, component TEXT, model TEXT,
    prompt_tokens INTEGER, completion_tokens INTEGER, cost_usd REAL, latency_ms REAL, status TEXT, error TEXT,
    created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_spans_run ON spans(run_id);
"""


def _conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


# ---------------------------------------------------------------- contracts
_STATUSES = {"baseline", "changed", "unchanged"}

CONTRACTS: dict[str, dict] = {
    "snapshot": {"kind": "node", "purpose": "Normalize DOM, hash, diff against stored snapshot",
                 "input": {"key": "str", "html": "str (non-empty)"},
                 "output": {"status": "baseline | changed | unchanged", "diff": "str"}},
    **{b: {"kind": "branch", "purpose": p, "input": {"html": "str (non-empty)"},
           "output": {"findings": "list[Finding] (never raises; failures become *-crashed / unavailable findings)"}}
       for b, p in {"a11y": "Accessibility via bundled a11y_service API", "validation": "Static HTML validation",
                    "links": "Link checks", "security": "Header / markup security checks",
                    "mcp_tests": "MCP automation test cases over stdio"}.items()},
    "merge": {"kind": "node", "purpose": "Dedupe findings by (source, rule_id, selector, message)",
              "input": {"findings": "list[Finding]"}, "output": {"findings": "list[Finding], no duplicates"}},
    "decide": {"kind": "node", "purpose": "Deterministic policy + guidelines; LLM only drafts patch text",
               "input": {"findings": "list[Finding]"},
               "output": {"findings": "every finding has decision; needs_human => review_status=pending; "
                                      "auto_suggest => non-empty suggested_fix"}},
    "report": {"kind": "node", "purpose": "Aggregate counts and serialize findings",
               "input": {"findings": "list[Finding]"},
               "output": {"report": "run_id, key, dom_status, total == len(findings), by_* counts, findings"}},
    "llm:patch_drafter": {"kind": "llm", "purpose": "Draft corrected HTML snippet for a guideline-backed finding",
                          "input": {"guideline.fix": "str", "finding.message": "str", "element": "str (untrusted)"},
                          "output": {"text": "HTML/JSX snippet only; falls back to guideline text on failure"}},
    "llm:rag_answerer": {"kind": "llm", "purpose": "Answer questions from retrieved findings + computed stats",
                         "input": {"STATS": "json", "CONTEXT": "numbered findings (untrusted)", "QUESTION": "str"},
                         "output": {"answer": "cited [n]; extractive fallback when LLM unavailable"}},
}


def check_input(node: str, state: dict) -> list[str]:
    v = []
    if node == "snapshot" and not (isinstance(state.get("key"), str) and isinstance(state.get("html"), str)):
        v.append("key/html must be str")
    elif CONTRACTS.get(node, {}).get("kind") == "branch" and not (isinstance(state.get("html"), str) and state["html"]):
        v.append("html must be a non-empty str")
    elif node in ("merge", "decide", "report") and not isinstance(state.get("findings", []), list):
        v.append("findings must be a list")
    return v


def check_output(node: str, out: dict, state: dict) -> list[str]:
    v: list[str] = []
    kind = CONTRACTS.get(node, {}).get("kind")
    fs = out.get("findings")
    if kind == "branch" or node in ("merge", "decide"):
        if not isinstance(fs, list):
            return ["findings missing or not a list"]
        bad = sum(1 for f in fs if not isinstance(f, Finding))
        if bad:
            v.append(f"{bad} non-Finding item(s)")
    if node == "snapshot" and out.get("status") not in _STATUSES:
        v.append(f"invalid status {out.get('status')!r}")
    if node == "merge" and isinstance(fs, list):
        keys = [(f.source, f.rule_id, f.selector, f.message) for f in fs if isinstance(f, Finding)]
        if len(keys) != len(set(keys)):
            v.append("duplicates remain after merge")
    if node == "decide" and isinstance(fs, list):
        for f in (x for x in fs if isinstance(x, Finding)):
            if f.decision == Decision.none:
                v.append(f"{f.rule_id}: no decision"); break
            if f.decision == Decision.needs_human and f.review_status != "pending":
                v.append(f"{f.rule_id}: needs_human but review_status={f.review_status}"); break
            if f.decision == Decision.auto_suggest and not f.suggested_fix:
                v.append(f"{f.rule_id}: auto_suggest without suggested_fix"); break
    if node == "report":
        r = out.get("report") or {}
        missing = [k for k in ("run_id", "key", "dom_status", "total", "by_decision", "findings") if k not in r]
        if missing:
            v.append(f"report missing {missing}")
        elif r["total"] != len(r["findings"]):
            v.append("report.total != len(findings)")
    return v


def summarize_in(node: str, state: dict) -> dict:
    s: dict = {}
    if isinstance(state.get("html"), str) and node in ("snapshot", *[k for k, c in CONTRACTS.items() if c["kind"] == "branch"]):
        s["html_bytes"] = len(state["html"].encode("utf-8", "ignore"))
    if node in ("merge", "decide", "report"):
        s["findings"] = len(state.get("findings") or [])
    return s


def summarize_out(node: str, out: dict) -> dict:
    s: dict = {}
    if "findings" in out and isinstance(out["findings"], list):
        s["findings"] = len(out["findings"])
        sev: dict[str, int] = {}
        for f in out["findings"]:
            if isinstance(f, Finding):
                sev[f.severity.value] = sev.get(f.severity.value, 0) + 1
        if sev:
            s["by_severity"] = sev
    if "status" in out:
        s["status"] = out["status"]
    if "report" in out:
        s["total"] = out["report"].get("total")
    return s


# ---------------------------------------------------------------- recording
def _insert(sql: str, args: tuple, db_path: str | None) -> None:
    try:
        with _conn(db_path) as c:
            c.execute(sql, args)
    except Exception:
        pass   # observability must never break the pipeline


def traced(node: str, fn, db_path_of=lambda s: s.get("db_path")):
    """Wrap a graph node fn(state)->dict with a span: timing, I/O summaries, contract checks, status."""
    def wrapper(s):
        run_id, db = s.get("run_id"), db_path_of(s)
        tok = _ctx.set((run_id, node))
        t0, out, err = time.perf_counter(), {}, None
        try:
            out = fn(s)
            return out
        except Exception as e:
            err = f"{e.__class__.__name__}: {e}"[:300]
            raise
        finally:
            _ctx.reset(tok)
            try:
                ms = (time.perf_counter() - t0) * 1000
                viol = check_input(node, s) + (check_output(node, out, s) if err is None else [])
                status = "error" if err else "ok"
                if not err:
                    rules = [f.rule_id for f in out.get("findings", []) if isinstance(f, Finding)] \
                        if CONTRACTS[node]["kind"] == "branch" else []
                    if any(r.endswith("-crashed") for r in rules):
                        status, err = "error", "branch crashed (converted to finding)"
                    elif any(r.endswith("-unavailable") for r in rules):
                        status, err = "degraded", "dependency unavailable"
                _insert("INSERT INTO spans(run_id,node,kind,duration_ms,status,input,output,contract_ok,violations,error)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (run_id, node, CONTRACTS[node]["kind"], ms, status, json.dumps(summarize_in(node, s)),
                         json.dumps(summarize_out(node, out)), 0 if viol else 1, json.dumps(viol), err), db)
            except Exception:
                pass
    return wrapper


def record_trace(run_id: str, key: str, dom_status: str | None, duration_ms: float, total: int,
                 error: str | None = None, db_path: str | None = None) -> None:
    _insert("INSERT OR REPLACE INTO traces(run_id,key,dom_status,duration_ms,total_findings,error) VALUES (?,?,?,?,?,?)",
            (run_id, key, dom_status, duration_ms, total, error), db_path)


def record_llm(component: str, model: str, usage, latency_ms: float, status: str = "ok",
               error: str | None = None, db_path: str | None = None) -> None:
    """usage: OpenAI-style usage object (or None). Stores token counts + estimated cost only."""
    pt = int(getattr(usage, "prompt_tokens", 0) or 0)
    ct = int(getattr(usage, "completion_tokens", 0) or 0)
    cost = pt / 1e6 * settings.llm_input_usd_per_mtok + ct / 1e6 * settings.llm_output_usd_per_mtok
    _insert("INSERT INTO llm_calls(run_id,component,model,prompt_tokens,completion_tokens,cost_usd,latency_ms,status,error)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (_ctx.get()[0], component, model, pt, ct, cost, latency_ms, status, (error or "")[:300] or None), db_path)


@contextmanager
def llm_timer():
    t = {"t0": time.perf_counter()}
    yield t
    t["ms"] = (time.perf_counter() - t["t0"]) * 1000


# ---------------------------------------------------------------- queries
def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    v = sorted(vals)
    return round(v[min(len(v) - 1, int(round(p * (len(v) - 1))))], 1)


def _rows(sql: str, args: tuple = (), db_path: str | None = None) -> list[dict]:
    with _conn(db_path) as c:
        return [dict(r) for r in c.execute(sql, args)]


def overview(limit: int = 500, db_path: str | None = None) -> dict:
    traces = _rows("SELECT * FROM traces ORDER BY created DESC, rowid DESC LIMIT ?", (limit,), db_path)
    spans = _rows("SELECT * FROM spans ORDER BY id DESC LIMIT ?", (limit * 8,), db_path)
    llm = _rows("SELECT * FROM llm_calls ORDER BY id DESC LIMIT ?", (limit * 4,), db_path)

    durs = [t["duration_ms"] for t in traces if t["duration_ms"] is not None]
    run_stats = {
        "runs": len(traces),
        "unchanged_skipped": sum(1 for t in traces if t["dom_status"] == "unchanged"),
        "errors": sum(1 for t in traces if t["error"]),
        "avg_ms": round(sum(durs) / len(durs), 1) if durs else 0.0,
        "p95_ms": _pct(durs, 0.95),
        "avg_findings": round(sum(t["total_findings"] or 0 for t in traces) / len(traces), 1) if traces else 0.0,
    }

    nodes: dict[str, dict] = {}
    for sp in spans:
        n = nodes.setdefault(sp["node"], {"node": sp["node"], "kind": sp["kind"], "calls": 0, "errors": 0,
                                          "degraded": 0, "contract_violations": 0, "_d": [], "findings": 0})
        n["calls"] += 1
        n["errors"] += sp["status"] == "error"
        n["degraded"] += sp["status"] == "degraded"
        n["contract_violations"] += not sp["contract_ok"]
        n["_d"].append(sp["duration_ms"] or 0)
        n["findings"] += (json.loads(sp["output"] or "{}").get("findings") or 0)
    node_rows = []
    for n in nodes.values():
        d = n.pop("_d")
        n["avg_ms"], n["p95_ms"], n["max_ms"] = round(sum(d) / len(d), 1), _pct(d, 0.95), round(max(d), 1)
        n["error_rate"] = round(n["errors"] / n["calls"], 3)
        node_rows.append(n)
    order = list(CONTRACTS)
    node_rows.sort(key=lambda r: order.index(r["node"]) if r["node"] in order else 99)

    comps: dict[str, dict] = {}
    for c in llm:
        k = comps.setdefault(c["component"], {"component": c["component"], "model": c["model"], "calls": 0,
                                              "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0,
                                              "failures": 0, "_l": []})
        k["calls"] += 1
        k["prompt_tokens"] += c["prompt_tokens"] or 0
        k["completion_tokens"] += c["completion_tokens"] or 0
        k["cost_usd"] += c["cost_usd"] or 0
        k["failures"] += c["status"] != "ok"
        k["_l"].append(c["latency_ms"] or 0)
    llm_rows = []
    for k in comps.values():
        l = k.pop("_l")
        k["avg_latency_ms"], k["p95_latency_ms"] = round(sum(l) / len(l), 1), _pct(l, 0.95)
        k["total_tokens"] = k["prompt_tokens"] + k["completion_tokens"]
        k["cost_usd"] = round(k["cost_usd"], 6)
        llm_rows.append(k)
    totals = {"calls": sum(r["calls"] for r in llm_rows), "failures": sum(r["failures"] for r in llm_rows),
              "prompt_tokens": sum(r["prompt_tokens"] for r in llm_rows),
              "completion_tokens": sum(r["completion_tokens"] for r in llm_rows),
              "cost_usd": round(sum(r["cost_usd"] for r in llm_rows), 6)}
    totals["total_tokens"] = totals["prompt_tokens"] + totals["completion_tokens"]
    totals["cost_per_run_usd"] = round(totals["cost_usd"] / run_stats["runs"], 6) if run_stats["runs"] else 0.0

    violations = [{"run_id": s["run_id"], "node": s["node"], "violations": json.loads(s["violations"] or "[]"),
                   "created": s["created"]} for s in spans if not s["contract_ok"]][:50]
    return {"runs": run_stats, "nodes": node_rows, "llm": llm_rows, "llm_totals": totals,
            "contract_violations": violations, "recent_traces": traces[:50],
            "recent_llm_calls": [{k: v for k, v in c.items() if k != "error" or v} for c in llm[:50]],
            "pricing": {"input_usd_per_mtok": settings.llm_input_usd_per_mtok,
                        "output_usd_per_mtok": settings.llm_output_usd_per_mtok, "model": settings.llm_model}}


def trace_detail(run_id: str, db_path: str | None = None) -> dict | None:
    t = _rows("SELECT * FROM traces WHERE run_id=?", (run_id,), db_path)
    if not t:
        return None
    spans = _rows("SELECT * FROM spans WHERE run_id=? ORDER BY id", (run_id,), db_path)
    for s in spans:
        s["input"], s["output"] = json.loads(s["input"] or "{}"), json.loads(s["output"] or "{}")
        s["violations"] = json.loads(s["violations"] or "[]")
    return {**t[0], "spans": spans, "llm_calls": _rows("SELECT * FROM llm_calls WHERE run_id=? ORDER BY id", (run_id,), db_path)}
