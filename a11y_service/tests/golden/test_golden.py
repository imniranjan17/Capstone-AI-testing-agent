import json
from pathlib import Path

import pytest

from app.agent.graph import run_analysis

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_case(graph, case):
    report = run_analysis(graph, "html", case["input"])
    matches = [f for f in report["findings"] if f["rule_id"] == case["expected_rule"] and f["verdict"] == case["expected_verdict"]]
    assert matches, f"{case['case_id']}: no {case['expected_verdict']} finding for {case['expected_rule']}"
    if case["expected_verdict"] == "FAIL":
        cited = {w["criterion"] for f in matches for w in f["wcag"]}
        assert cited & set(case["expected_criteria"]), cited
        assert not cited & set(case["forbidden_criteria"])
    # No unsupported PASS: a PASS must come from an executed deterministic check.
    for f in report["findings"]:
        if f["verdict"] == "PASS":
            assert "deterministic_rule" in f["evidence_types"]
