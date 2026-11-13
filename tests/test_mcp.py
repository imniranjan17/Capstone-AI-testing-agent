from app.branches.mcp_tests import results_to_findings, run_mcp_tests

BAD = '<html><body><nav><a href="#">Home</a></nav><form action="#"><input name="a"></form></body></html>'
GOOD = ('<html lang="en"><head><title>T</title></head><body><h1>H</h1><nav><a href="/a">A</a></nav>'
        '<form action="/x"><button>Go</button></form></body></html>')


def test_mapping():
    fs = results_to_findings([{"test": "t", "passed": False, "details": ["x", "y"]}, {"test": "u", "passed": True}])
    assert [f.message for f in fs] == ["x", "y"] and fs[0].rule_id == "mcp-t"


def test_real_server_bad_page():
    rules = {f.rule_id for f in run_mcp_tests(BAD)}
    assert {"mcp-check_form_submit", "mcp-check_nav_links", "mcp-check_page_basics"} <= rules


def test_real_server_good_page():
    assert run_mcp_tests(GOOD) == []
