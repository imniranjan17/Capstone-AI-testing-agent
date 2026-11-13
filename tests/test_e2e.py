"""End-to-end with REAL branches (a11y service intentionally offline -> graceful finding)."""
from pathlib import Path

from app import store
from app.config import settings
from app.graph import run_pipeline

DEMO = Path(__file__).resolve().parent.parent / "demo"


def test_demo_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "a11y_api_url", "http://127.0.0.1:9")
    db = str(tmp_path / "e2e.db")
    v1 = (DEMO / "page_v1.html").read_text(encoding="utf-8")
    v2 = (DEMO / "page_v2.html").read_text(encoding="utf-8")

    base = run_pipeline("shop", v1, db_path=db)
    assert base["dom_status"] == "baseline"
    assert not {f["rule_id"] for f in base["findings"]} & {"broken-link", "blank-no-noopener", "input-wrong-type"}

    assert run_pipeline("shop", v1, db_path=db)["dom_status"] == "unchanged"

    rep = run_pipeline("shop", v2, db_path=db)
    assert rep["dom_status"] == "changed" and "img" in rep["diff"]
    by_rule = {f["rule_id"]: f for f in rep["findings"]}
    for rule in ("broken-link", "blank-no-noopener", "inline-handler", "input-wrong-type", "password-in-get",
                 "link-empty-href", "mcp-check_nav_links", "mcp-check_page_basics", "mcp-check_form_submit",
                 "a11y-service-unavailable"):
        assert rule in by_rule, rule
    assert by_rule["blank-no-noopener"]["decision"] == "needs_human"     # security -> always human
    assert "noopener" in by_rule["blank-no-noopener"]["suggested_fix"]
    assert by_rule["input-wrong-type"]["decision"] == "auto_suggest"
    assert by_rule["password-in-get"]["decision"] == "needs_human"       # security
    assert by_rule["broken-link"]["decision"] == "needs_human"           # guideline says human
    assert by_rule["mcp-check_nav_links"]["decision"] == "needs_human"

    pend = store.pending_reviews(rep["run_id"], db)
    assert pend and all(p["review_status"] == "pending" for p in pend)
    store.review(rep["run_id"], pend[0]["idx"], "rejected", db_path=db)
    assert len(store.pending_reviews(rep["run_id"], db)) == len(pend) - 1
