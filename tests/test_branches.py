from app.branches.links import run_links
from app.branches.security import run_security
from app.branches.validation import run_validation

FORM = """<form method="get" action="http://x.com/login"><input name="email" type="text">
<input type="password" name="pw"><input type="text"></form>"""


def rules(fs):
    return {f.rule_id for f in fs}


def test_validation():
    r = rules(run_validation(FORM))
    assert {"form-no-submit", "form-no-required", "input-wrong-type", "input-no-name",
            "password-no-constraints"} <= r


def test_security():
    html = FORM + '<a href="/a" target="_blank" onclick="x()">a</a>'
    r = rules(run_security(html, headers={}, base_url="https://s.com"))
    assert {"missing-header", "password-in-get", "insecure-url", "blank-no-noopener", "inline-handler"} <= r


def test_links():
    html = '<a href="/ok">1</a><a href="/missing">2</a><a href="#">3</a><img src="https://c.com/i.png">'
    fake = lambda u: 404 if "missing" in u else 200
    fs = run_links(html, "https://s.com", checker=fake)
    assert rules(fs) == {"broken-link", "link-empty-href"}
    assert [f for f in fs if f.rule_id == "broken-link"][0].message.startswith("https://s.com/missing")
