"""Turn stored runs into searchable documents (one per finding + one summary per page)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app import store


@dataclass
class Doc:
    doc_id: str
    text: str
    meta: dict = field(default_factory=dict)


def domain_of(key: str) -> str:
    """URL key -> host (my-product.com); pasted/demo keys -> 'pasted'."""
    if key.lower().startswith(("http://", "https://")):
        return urlparse(key).netloc.lower() or "pasted"
    return "pasted"


def latest_runs(db_path: str | None = None) -> list[dict]:
    """Newest run per page key (a page's current state)."""
    with store._conn(db_path) as c:
        rows = c.execute("""SELECT run_id FROM runs r WHERE rowid = (
            SELECT MAX(rowid) FROM runs WHERE key = r.key)""").fetchall()
    return [r for r in (store.get_run(x["run_id"], db_path) for x in rows) if r]


def build_docs(db_path: str | None = None, domain: str | None = None) -> list[Doc]:
    docs: list[Doc] = []
    for rep in latest_runs(db_path):
        dom = domain_of(rep["key"])
        if domain and dom != domain:
            continue
        base = {"domain": dom, "page": rep["key"], "run_id": rep["run_id"]}
        sev = rep.get("by_severity", {})
        docs.append(Doc(f"{rep['run_id']}#summary", (
            f"Page summary for {rep['key']} (domain {dom}). DOM status: {rep['dom_status']}. "
            f"Total findings: {rep.get('total', 0)}. By category: {rep.get('by_category', {})}. "
            f"By severity: {sev}. By decision: {rep.get('by_decision', {})}."),
            {**base, "kind": "summary"}))
        for f in rep["findings"]:
            review = f.get("review_status", "n/a")
            text = (f"Page {rep['key']} | {f['category']} issue | severity {f['severity']} | rule {f['rule_id']} | "
                    f"{f['message']} | element {f.get('selector') or 'n/a'} | evidence {f.get('evidence') or ''} | "
                    f"decision {f.get('decision')} ({f.get('decision_reason') or ''}) | review status {review} | "
                    f"suggested fix: {f.get('suggested_fix') or 'none'}")
            docs.append(Doc(f"{rep['run_id']}#{f['idx']}", text, {
                **base, "kind": "finding", "idx": f["idx"], "category": f["category"], "severity": f["severity"],
                "rule_id": f["rule_id"], "decision": f.get("decision"), "review_status": review}))
    return docs


def domain_stats(db_path: str | None = None, domain: str | None = None) -> dict:
    """Exact counts (RAG can't count reliably, so these are computed, not retrieved)."""
    pages, cat, sev, dec = {}, {}, {}, {}
    for rep in latest_runs(db_path):
        if domain and domain_of(rep["key"]) != domain:
            continue
        pages[rep["key"]] = rep.get("total", 0)
        for f in rep["findings"]:
            for d, k in ((cat, f["category"]), (sev, f["severity"]), (dec, f.get("decision"))):
                d[k] = d.get(k, 0) + 1
    return {"domain": domain or "all", "pages": pages, "page_count": len(pages),
            "total_findings": sum(pages.values()), "by_category": cat, "by_severity": sev, "by_decision": dec}


def list_domains(db_path: str | None = None) -> list[str]:
    return sorted({domain_of(r["key"]) for r in latest_runs(db_path)})
