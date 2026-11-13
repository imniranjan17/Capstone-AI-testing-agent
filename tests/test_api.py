import pytest
from fastapi.testclient import TestClient

from app import api
from app.config import settings
from app.graph import build_graph
from app.policy import make_decider
from app.schemas import Category, Finding, Severity


def F(rule, cat=Category.accessibility):
    return Finding(source="x", category=cat, severity=Severity.medium, rule_id=rule, message="m")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "api.db"))
    monkeypatch.setattr(api, "_graph", build_graph(
        {"v": lambda s: [F("image-alt"), F("missing-header", Category.security)]}, decide=make_decider()))
    return TestClient(api.app)


def test_validation_errors(client):
    assert client.post("/runs", json={}).status_code == 422
    assert client.post("/runs", json={"html": "<p/>", "url": "https://a.com"}).status_code == 422
    assert client.post("/runs", json={"url": "file:///etc/passwd"}).status_code == 422


def test_full_flow(client):
    r = client.post("/runs", json={"html": "<p>x</p>"}).json()
    assert r["dom_status"] == "baseline" and r["by_decision"] == {"auto_suggest": 1, "needs_human": 1}
    assert client.post("/runs", json={"html": "<p>x</p>"}).json()["dom_status"] == "unchanged"
    pend = client.get("/reviews/pending").json()
    assert len(pend) == 1
    rv = client.post(f"/runs/{r['run_id']}/review", json={"idx": pend[0]["idx"], "status": "approved"})
    assert rv.json()["review_status"] == "approved"
    assert client.post(f"/runs/{r['run_id']}/review", json={"idx": pend[0]["idx"], "status": "approved"}).status_code == 409
    assert client.post(f"/runs/{r['run_id']}/review", json={"idx": 99, "status": "approved"}).status_code == 404
    assert client.get("/reviews/pending").json() == []
    assert len(client.get("/runs").json()) == 2
    assert client.get(f"/runs/{r['run_id']}").json()["total"] == 2
    assert client.get("/runs/nope").status_code == 404
