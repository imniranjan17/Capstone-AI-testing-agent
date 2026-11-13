from app.graph import build_graph, run_pipeline
from app.policy import load_guidelines, make_decider
from app.schemas import Category, Decision, Finding, Severity


def F(rule, cat=Category.accessibility, sev=Severity.medium, src="a11y", sel=None):
    return Finding(source=src, category=cat, severity=sev, rule_id=rule, message="m", selector=sel)


def decide(fs):
    return make_decider()(fs)


def test_guidelines_load():
    assert "react-missing-key" in load_guidelines()


def test_auto_suggest_low_risk():
    r = decide([F("react-missing-key"), F("image-alt", sev=Severity.critical)])
    assert all(f.decision == Decision.auto_suggest and f.review_status == "n/a" and f.suggested_fix for f in r)


def test_human_cases():
    r = {f.rule_id: f for f in decide([
        F("missing-header", Category.security, Severity.low, "security"),
        F("unknown-rule"),
        F("color-contrast", sev=Severity.low),
        F("react-missing-key", sev=Severity.high),                 # above guideline max_severity
        F("mcp-check_form_submit", Category.functional, Severity.high, "mcp"),
    ])}
    assert all(f.decision == Decision.needs_human and f.review_status == "pending" for f in r.values())
    assert "no guideline" in r["unknown-rule"].decision_reason


def test_related_mcp_failure_blocks_auto():
    r = decide([F("image-alt", sel="img#hero"), F("mcp-x", Category.functional, Severity.high, "mcp", sel="img#hero")])
    assert r[0].decision == Decision.needs_human and "automation test" in r[0].decision_reason


def test_drafter_used_only_for_auto():
    d = make_decider(drafter=lambda f, g: "DRAFT")
    r = d([F("image-alt"), F("color-contrast")])
    assert r[0].suggested_fix == "DRAFT" and r[1].suggested_fix != "DRAFT"


def test_graph_integration(tmp_path):
    g = build_graph({"v": lambda s: [F("react-missing-key"), F("missing-header", Category.security)]},
                    decide=make_decider())
    r = run_pipeline("k", "<p/>", db_path=str(tmp_path / "p.db"), graph=g)
    assert r["by_decision"] == {"auto_suggest": 1, "needs_human": 1}
