"""Step 6: LangGraph pipeline — snapshot -> (parallel branches) -> merge -> decide -> report."""
from __future__ import annotations

import time
import uuid
from typing import Annotated, Callable, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from app.branches.a11y import run_a11y
from app.branches.links import run_links
from app.branches.mcp_tests import run_mcp_tests
from app.branches.security import run_security
from app.branches.validation import run_validation
from app.patches import draft_patch
from app.policy import make_decider
from app.schemas import Finding
from app import observability as obs
from app import store
from app.snapshot import detect_change


class _Replace(list):
    """Marker: merge/decide replace the accumulated list instead of appending."""


def _reduce(old: list, new: list) -> list:
    return list(new) if isinstance(new, _Replace) else (old or []) + (new or [])


class State(TypedDict, total=False):
    run_id: str
    key: str                      # URL or demo name (snapshot key)
    html: str
    base_url: str
    headers: dict[str, str] | None
    force: bool                   # run checks even if DOM unchanged
    db_path: str | None
    status: str                   # baseline | changed | unchanged
    diff: str
    findings: Annotated[list[Finding], _reduce]   # branches append in parallel
    report: dict


def default_branches(state: State) -> dict[str, Callable[[State], list[Finding]]]:
    return {
        "a11y": lambda s: run_a11y(s["html"]),
        "validation": lambda s: run_validation(s["html"]),
        "links": lambda s: run_links(s["html"], s.get("base_url", "")),
        "security": lambda s: run_security(s["html"], s.get("headers"), s.get("base_url", "")),
        "mcp_tests": lambda s: run_mcp_tests(s["html"]),
    }


def build_graph(branches: dict[str, Callable[[State], list[Finding]]] | None = None, decide=None):
    branches = branches or default_branches({})
    decide = decide or make_decider(drafter=draft_patch)

    def snapshot(s: State) -> dict:
        r = detect_change(s["key"], s["html"], s.get("db_path"))
        return {"status": r.status, "diff": r.diff}

    def route(s: State):
        if s["status"] == "unchanged" and not s.get("force"):
            return END
        return list(branches)

    def make_branch(name: str, fn):
        def node(s: State) -> dict:
            try:
                return {"findings": fn(s)}
            except Exception as e:  # a branch must never break the run
                from app.schemas import Category, Severity
                return {"findings": [Finding(source=name, category=Category.functional, severity=Severity.low,
                                             rule_id=f"{name}-crashed", message=f"{e.__class__.__name__}: {e}")]}
        return node

    def merge(s: State) -> dict:
        seen, out = set(), []
        for f in s.get("findings", []):
            k = (f.source, f.rule_id, f.selector, f.message)
            if k not in seen:
                seen.add(k)
                out.append(f)
        return {"findings": _Replace(out)}

    def decide_node(s: State) -> dict:
        return {"findings": _Replace(decide(s["findings"]))}

    def report(s: State) -> dict:
        fs = s.get("findings", [])
        def by(attr):
            vals = [getattr(f, attr) for f in fs]
            vals = [getattr(v, "value", v) for v in vals]
            return {v: vals.count(v) for v in set(vals)}
        return {"report": {
            "run_id": s["run_id"], "key": s["key"], "dom_status": s["status"], "forced": bool(s.get("force")), "diff": s.get("diff", ""),
            "total": len(fs), "by_category": by("category"), "by_severity": by("severity"),
            "by_decision": by("decision"), "findings": [f.model_dump(mode="json") for f in fs],
        }}

    g = StateGraph(State)
    g.add_node("snapshot", obs.traced("snapshot", snapshot))
    for name, fn in branches.items():
        node = make_branch(name, fn)
        g.add_node(name, obs.traced(name, node) if name in obs.CONTRACTS else node)
    g.add_node("merge", obs.traced("merge", merge))
    g.add_node("decide", obs.traced("decide", decide_node))
    g.add_node("report", obs.traced("report", report))
    g.add_edge(START, "snapshot")
    g.add_conditional_edges("snapshot", route, [*branches, END])
    g.add_edge(list(branches), "merge")          # waits for ALL branches
    g.add_edge("merge", "decide")
    g.add_edge("decide", "report")
    g.add_edge("report", END)
    return g.compile()


def run_pipeline(key: str, html: str | None = None, url: str | None = None, force: bool = False,
                 db_path: str | None = None, graph=None) -> dict:
    headers = None
    run_id, t0 = str(uuid.uuid4()), time.perf_counter()
    try:
        if url:
            r = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "web-testing-agent/0.1"})
            r.raise_for_status()
            html, headers, key = r.text, dict(r.headers), key or url
        if html is None:
            raise ValueError("provide html or url")
        graph = graph or build_graph()
        out = graph.invoke({"run_id": run_id, "key": key or "demo", "html": html, "base_url": url or "",
                            "headers": headers, "force": force, "db_path": db_path, "findings": []})
        report = out.get("report") or {"run_id": run_id, "key": out["key"], "dom_status": "unchanged",
                                       "total": 0, "findings": [], "diff": ""}
        store.save_run(report, db_path)
    except Exception as e:
        obs.record_trace(run_id, key or url or "demo", None, (time.perf_counter() - t0) * 1000, 0,
                         f"{e.__class__.__name__}: {e}"[:300], db_path)
        raise
    obs.record_trace(run_id, report["key"], report["dom_status"], (time.perf_counter() - t0) * 1000,
                     report.get("total", 0), None, db_path)
    return report
