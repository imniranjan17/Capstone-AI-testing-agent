import pytest

from app import store
from app.graph import build_graph, run_pipeline
from app.policy import make_decider
from app.schemas import Category, Finding, Severity


def F(rule, cat=Category.accessibility, sev=Severity.medium):
    return Finding(source="x", category=cat, severity=sev, rule_id=rule, message="m")


@pytest.fixture
def run(tmp_path):
    db = str(tmp_path / "s.db")
    g = build_graph({"v": lambda s: [F("image-alt"), F("missing-header", Category.security), F("color-contrast")]},
                    decide=make_decider())
    return run_pipeline("k", "<p/>", db_path=db, graph=g), db


def test_persist_and_pending(run):
    rep, db = run
    got = store.get_run(rep["run_id"], db)
    assert got["total"] == 3 and len(got["findings"]) == 3
    pend = store.pending_reviews(db_path=db)
    assert {f["rule_id"] for f in pend} == {"missing-header", "color-contrast"}
    assert store.list_runs("k", db_path=db)[0]["run_id"] == rep["run_id"]


def test_review_flow(run):
    rep, db = run
    p = store.pending_reviews(db_path=db)[0]
    r = store.review(rep["run_id"], p["idx"], "approved", "ok", final_fix="edited", db_path=db)
    assert r["review_status"] == "approved" and r["final_fix"] == "edited"
    assert len(store.pending_reviews(db_path=db)) == 1
    with pytest.raises(ValueError):
        store.review(rep["run_id"], p["idx"], "rejected", db_path=db)      # already reviewed
    with pytest.raises(ValueError):
        store.review(rep["run_id"], 99, "maybe", db_path=db)
    with pytest.raises(KeyError):
        store.review(rep["run_id"], 99, "approved", db_path=db)
