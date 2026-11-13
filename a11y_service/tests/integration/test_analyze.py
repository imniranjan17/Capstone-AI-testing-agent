import pytest
from fastapi.testclient import TestClient

from app.agent.graph import build_graph, run_analysis
from app.api.deps import set_graph
from app.main import app
from tests.conftest import FakeLLM

DEMO = """<html>
<head><title>Search</title></head>
<body>
<main>
<img src="logo.png">
<label>Email</label>
<input type="email">
<button><svg aria-hidden="true"></svg></button>
</main>
</body>
</html>"""

ALLOWED = {"PASS", "FAIL", "MANUAL_REVIEW", "INSUFFICIENT_EVIDENCE"}


def verdicts(report, rule):
    return [f["verdict"] for f in report["findings"] if f["rule_id"] == rule]


def test_demo_html(graph):
    r = run_analysis(graph, "html", DEMO)
    assert r["overall_verdict"] == "FAIL"
    assert "FAIL" in verdicts(r, "html-has-lang")
    assert "FAIL" in verdicts(r, "image-alt")
    assert "FAIL" in verdicts(r, "label")
    assert "FAIL" in verdicts(r, "button-name")
    assert "MANUAL_REVIEW" in verdicts(r, "image-alt-quality")
    assert "complete WCAG conformance" in r["scope"]["limitation"]
    assert {f["verdict"] for f in r["findings"]} <= ALLOWED
    assert r["retrieval_debug"] is None
    for f in r["findings"]:
        if f["verdict"] == "FAIL":
            assert f["wcag"], "every FAIL needs traceable WCAG evidence"
            assert all(w["source_url"] for w in f["wcag"])


def test_button_maps_to_4_1_2(graph):
    r = run_analysis(graph, "html", "<button><svg></svg></button>")
    f = next(f for f in r["findings"] if f["rule_id"] == "button-name")
    assert [w["criterion"] for w in f["wcag"]] == ["4.1.2"]


def test_clean_fragment_never_claims_conformance(graph):
    r = run_analysis(graph, "html", '<button>Save</button>')
    assert r["overall_verdict"] in {"MANUAL_REVIEW", "PASS_WITH_SCOPE_LIMITATION"}
    assert r["overall_verdict"] != "PASS"
    assert r["summary"]["failed"] == 0


def test_all_pass_overall(graph):
    r = run_analysis(graph, "html", '<a href="/x">Pricing</a>'.replace("<a", "<p>text</p><a"))
    # interactive content adds manual items, so overall is MANUAL_REVIEW, never a bare PASS
    assert r["overall_verdict"] == "MANUAL_REVIEW"


def test_axe_report(graph):
    content = {"url": "https://example.test/checkout", "violations": [{
        "id": "button-name", "impact": "serious", "description": "Ensure buttons have discernible text",
        "nodes": [{"html": "<button><svg></svg></button>", "target": ["button"]}]}]}
    r = run_analysis(graph, "axe_report", content)
    assert r["overall_verdict"] == "FAIL"
    assert r["findings"][0]["wcag"][0]["criterion"] == "4.1.2"
    assert "report_evidence" in r["findings"][0]["evidence_types"]


def test_generic_report_and_unknown_rule(graph):
    content = {"findings": [
        {"rule": "button-name", "impact": "serious", "element": "<button></button>", "message": "no name"},
        {"rule": "totally-made-up-rule", "message": "weird"},
    ]}
    r = run_analysis(graph, "report", content)
    assert verdicts(r, "button-name") == ["FAIL"]
    assert verdicts(r, "totally-made-up-rule") == ["INSUFFICIENT_EVIDENCE"]


def test_empty_knowledge_base_gives_insufficient_evidence():
    from app.retrieval.service import Retriever

    g = build_graph(Retriever([]), None)
    r = run_analysis(g, "html", "<button></button>")
    assert verdicts(r, "button-name") == ["INSUFFICIENT_EVIDENCE"]
    assert r["overall_verdict"] != "FAIL"


def test_llm_explanation_drops_fabricated_criteria(retriever):
    g = build_graph(retriever, FakeLLM())
    r = run_analysis(g, "html", "<button><svg></svg></button>")
    f = next(f for f in r["findings"] if f["rule_id"] == "button-name")
    assert f["reason"] == "Because evidence." and f["recommendation"] == "Fix it."
    assert all(w["criterion"] != "9.9.9" for w in f["wcag"])


def test_invalid_llm_output_does_not_change_verdict(retriever):
    llm = FakeLLM(reply="not json at all")
    g = build_graph(retriever, llm)
    r = run_analysis(g, "html", "<button><svg></svg></button>")
    f = next(f for f in r["findings"] if f["rule_id"] == "button-name")
    assert f["verdict"] == "FAIL" and f["recommendation"] == ""
    assert any("invalid output" in w for w in r["warnings"])
    assert llm.calls >= 2  # one repair retry


def test_debug_output_only_when_requested(graph):
    r = run_analysis(graph, "html", "<button></button>", debug=True)
    assert r["retrieval_debug"] and r["retrieval_debug"]["fused"]


def test_unsupported_target_rejected(graph):
    with pytest.raises(ValueError):
        run_analysis(graph, "html", "<p>x</p>", target_standard="WCAG_9_9")


@pytest.fixture
def client(graph):
    set_graph(graph)
    yield TestClient(app)
    set_graph(None)


def test_api_analyze_and_runs(client):
    resp = client.post("/v1/analyze", json={"input_type": "html", "target_standard": "WCAG_2_2_AA", "content": DEMO})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall_verdict"] == "FAIL" and body["retrieval_debug"] is None
    assert resp.headers["x-request-id"]
    stored = client.get(f"/v1/runs/{body['run_id']}")
    assert stored.status_code == 200 and stored.json()["run_id"] == body["run_id"]
    html = client.get(f"/v1/runs/{body['run_id']}?format=html")
    assert "&lt;img" in html.text and "<img" not in html.text  # input markup escaped
    assert client.get("/v1/runs/nope").status_code == 404


def test_api_validation_errors_are_422(client):
    assert client.post("/v1/analyze", json={"input_type": "html"}).status_code == 422
    assert client.post("/v1/analyze", json={"input_type": "nope", "content": "x"}).status_code == 422
    assert client.post("/v1/analyze", content="{bad json", headers={"content-type": "application/json"}).status_code == 422


def test_api_payload_limit(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_payload_bytes", 100)
    big = {"input_type": "html", "content": "<p>" + "x" * 500 + "</p>"}
    assert client.post("/v1/analyze", json=big).status_code == 413


def test_health(client):
    body = client.get("/health").json()
    assert body["api"] == "ok" and "models" in body and "vector_db" in body
