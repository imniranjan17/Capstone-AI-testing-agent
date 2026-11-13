"""Step 4a: form validation checks (static, no JS)."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.schemas import Category, Finding, Severity

_HINT = {"email": "email", "tel": "tel", "phone": "tel", "url": "url", "age": "number", "date": "date"}


def _sel(el) -> str:
    return el.name + (f"#{el['id']}" if el.get("id") else f"[name={el['name']}]" if el.get("name") else "")


def run_validation(html: str) -> list[Finding]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Finding] = []

    def add(rule, sev, msg, el):
        out.append(Finding(source="validation", category=Category.validation, severity=sev,
                           rule_id=rule, message=msg, selector=_sel(el), evidence=str(el)[:160]))

    for form in soup.find_all("form"):
        has_submit = form.find("input", attrs={"type": "submit"}) or any(
            (b.get("type") or "submit") == "submit" for b in form.find_all("button"))
        if not has_submit:
            add("form-no-submit", Severity.medium, "Form has no submit button", form)
        fields = form.find_all(["input", "select", "textarea"])
        if fields and not any(f.has_attr("required") for f in fields):
            add("form-no-required", Severity.low, "No field in the form is marked required", form)
        for f in fields:
            t = (f.get("type") or "text").lower()
            if t in ("hidden", "submit", "button", "reset", "image"):
                continue
            if not f.get("name"):
                add("input-no-name", Severity.medium, "Input has no name; value will not be submitted", f)
            key = (f.get("name") or f.get("id") or "").lower()
            if t == "text":
                tokens = set(re.split(r"[^a-z0-9]+", key))
                for k, expected in _HINT.items():
                    if k in tokens:
                        add("input-wrong-type", Severity.medium,
                            f"Field '{key}' looks like {expected} but uses type=text (no browser validation)", f)
                        break
            if t == "password" and not f.get("minlength") and not f.get("pattern"):
                add("password-no-constraints", Severity.low, "Password field has no minlength/pattern", f)
    return out
