from app.branches.a11y import report_to_findings, run_a11y

REPORT = {"findings": [
    {"verdict": "FAIL", "rule_id": "image-alt", "impact": "critical", "selector": "img", "observation": "img lacks alt",
     "recommendation": "Add alt", "wcag": [{"criterion": "1.1.1"}]},
    {"verdict": "PASS", "rule_id": "html-lang", "observation": "ok"}],
    "manual_review_items": [{"verdict": "MANUAL_REVIEW", "rule_id": "focus-order", "observation": "check focus"}]}


def test_mapping():
    fs = report_to_findings(REPORT)
    assert [f.rule_id for f in fs] == ["image-alt", "focus-order"]
    assert fs[0].severity == "critical" and "1.1.1" in fs[0].evidence
    assert fs[1].severity == "low"


def test_service_down_is_graceful():
    fs = run_a11y("<p>x</p>", api_url="http://127.0.0.1:9", timeout=2)
    assert fs[0].rule_id == "a11y-service-unavailable"
