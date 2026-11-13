import pytest
from fastapi.testclient import TestClient

from app import api, observability as obs
from app.config import settings
from app.graph import build_graph
from app.policy import make_decider
from app.schemas import Category, Finding, Severity


def F(rule, cat=Category.accessibility):
    return Finding(source="x", category=cat, severity=Severity.medium, rule_id=rule, message="m")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "o.db"))
    monkeypatch.setattr(api, "_graph", build_graph(
        {"a11y": lambda s: [F("image-alt")], "links": lambda s: 1 / 0}, decide=make_decider()))
    return TestClient(api.app)


def test_spans_traces_and_errors(client):
    r = client.post("/runs", json={"html": "<p>x</p>"}).json()
    d = client.get(f"/audit/traces/{r['run_id']}").json()
    nodes = {s["node"]: s for s in d["spans"]}
    assert {"snapshot", "a11y", "links", "merge", "decide", "report"} <= set(nodes)
    assert nodes["links"]["status"] == "error"          # crash converted to finding, flagged in span
    assert all(s["contract_ok"] for s in d["spans"])
    ov = client.get("/audit/overview").json()
    assert ov["runs"]["runs"] == 1 and any(n["node"] == "links" and n["errors"] == 1 for n in ov["nodes"])
    assert client.get("/audit/traces/nope").status_code == 404
    assert "decide" in client.get("/audit/contracts").json()


def test_contract_violation_detected():
    out = {"findings": [F("a").model_copy(), "not-a-finding"]}
    assert obs.check_output("a11y", out, {})
    assert obs.check_output("decide", {"findings": [F("a")]}, {})   # decision still none


def test_llm_cost(tmp_path):
    class U: prompt_tokens, completion_tokens = 1_000_000, 1_000_000
    db = str(tmp_path / "l.db")
    obs.record_llm("llm:rag_answerer", "m", U(), 12.0, db_path=db)
    t = obs.overview(db_path=db)["llm_totals"]
    assert t["total_tokens"] == 2_000_000 and t["cost_usd"] == pytest.approx(
        settings.llm_input_usd_per_mtok + settings.llm_output_usd_per_mtok)
