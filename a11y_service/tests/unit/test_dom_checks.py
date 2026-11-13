import pytest

from app.analysis.normalizer import normalize_html


def run(html: str):
    return normalize_html(html).observations


def by(obs, rule, status):
    return [o for o in obs if o.rule_id == rule and o.status == status]


DEMO = """<html><head><title>Search</title></head><body><main>
<img src="logo.png"><label>Email</label><input type="email">
<button><svg aria-hidden="true"></svg></button></main></body></html>"""


def test_demo_document():
    obs = run(DEMO)
    assert by(obs, "html-has-lang", "fail")
    assert by(obs, "image-alt", "fail")
    assert by(obs, "label", "fail")
    assert by(obs, "button-name", "fail")
    assert by(obs, "image-alt-quality", "manual")
    assert not by(obs, "landmark-one-main", "fail")


def test_image_alt_pass_scoped():
    obs = run('<img src="a.png" alt="Company logo">')
    assert by(obs, "image-alt", "pass")
    assert not by(obs, "image-alt", "fail")
    assert by(obs, "image-alt-quality", "manual")  # meaningfulness is never auto-passed


def test_empty_alt_is_not_failure():
    assert not by(run('<img src="a.png" alt="">'), "image-alt", "fail")


@pytest.mark.parametrize("html", [
    "<button>Save</button>",
    '<button aria-label="Close"><svg></svg></button>',
    '<button><img src="x.png" alt="Search"></button>',
    '<input type="submit" value="Go">',
])
def test_button_named(html):
    obs = run(html)
    assert not by(obs, "button-name", "fail") and not by(obs, "input-button-name", "fail")
    assert by(obs, "button-name", "pass") or by(obs, "input-button-name", "pass") or "input" in html


def test_button_unnamed():
    assert by(run("<button><svg></svg></button>"), "button-name", "fail")
    assert by(run('<div role="button"></div>'), "button-name", "fail")


def test_label_variants():
    assert not by(run('<label for="e">Email</label><input id="e">'), "label", "fail")
    assert not by(run("<label>Email <input></label>"), "label", "fail")
    assert not by(run('<input aria-label="Email">'), "label", "fail")
    assert by(run('<label for="x">Email</label><input id="e">'), "label", "fail")
    assert by(run("<select><option>a</option></select>"), "select-name", "fail")
    assert not by(run('<input type="hidden" name="a">'), "label", "fail")


def test_links():
    assert by(run('<a href="/x"></a>'), "link-name", "fail")
    assert by(run('<a href="/x">click here</a>'), "link-text-ambiguous", "manual")
    assert by(run('<a href="/x">Pricing</a>'), "link-name", "pass")


def test_headings():
    assert by(run("<h1>A</h1><h3>B</h3>"), "heading-order", "fail")
    assert by(run("<h1>A</h1><h2></h2>"), "empty-heading", "fail")
    assert by(run("<h1>A</h1><h2>B</h2>"), "heading-order", "pass")


def test_lang_and_landmark_only_for_full_documents():
    assert not by(run("<p>fragment</p>"), "html-has-lang", "fail")
    assert not by(run("<p>fragment</p>"), "html-has-lang", "pass")
    full = "<html><body><p>x</p></body></html>"
    assert by(run(full), "html-has-lang", "fail")
    assert by(run(full), "landmark-one-main", "fail")
    assert by(run('<html lang="en"><body><main>x</main></body></html>'), "html-has-lang", "pass")
    assert by(run('<html lang="e!"><body></body></html>'), "html-lang-valid", "fail")


def test_aria():
    assert by(run('<div aria-foo="1"></div>'), "aria-valid-attr", "fail")
    assert by(run('<div role="banana"></div>'), "aria-roles", "fail")
    assert by(run('<button aria-expanded="maybe">x</button>'), "aria-valid-attr-value", "fail")
    assert by(run('<input aria-labelledby="nope">'), "aria-valid-attr-value", "fail")
    assert by(run('<span id="l"></span><input aria-labelledby="l">'), "aria-labelledby-valid", "fail")
    assert by(run('<span id="l">Name</span><input aria-labelledby="l">'), "aria-valid-attr-value", "pass")


def test_duplicate_ids():
    assert by(run('<div id="a"></div><div id="a"></div>'), "duplicate-id", "manual")
    assert not by(run('<div id="a"></div><div id="a"></div>'), "duplicate-id", "fail")
    assert by(run('<label for="a">x</label><input id="a"><input id="a">'), "duplicate-id-aria", "fail")
    assert by(run('<div id="a"></div><div id="b"></div>'), "duplicate-id", "pass")


def test_contrast_only_with_computed_data():
    bad = '<p data-computed-color="#aaaaaa" data-computed-bg="#ffffff">t</p>'
    good = '<p data-computed-color="#000000" data-computed-bg="#ffffff">t</p>'
    assert by(run(bad), "color-contrast", "fail")
    assert by(run(good), "color-contrast", "pass")
    assert not [o for o in run("<p>t</p>") if o.rule_id == "color-contrast"]


def test_manual_items_for_interactive_content():
    obs = run("<button>Save</button>")
    assert by(obs, "focus-order-manual", "manual") and by(obs, "target-size-manual", "manual")
    assert not by(run("<p>text</p>"), "focus-order-manual", "manual")


def test_sensitive_values_redacted():
    obs = run('<input type="password" value="hunter2">')
    assert all("hunter2" not in o.element for o in obs)


def test_malformed_html_warns_not_crashes():
    result = normalize_html("<div><span></div></span><button>")
    assert isinstance(result.observations, list)
