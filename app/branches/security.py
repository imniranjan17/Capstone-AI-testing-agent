"""Step 4c: static security checks (headers + markup). Only scan sites you are authorized to test."""
from __future__ import annotations

from bs4 import BeautifulSoup

from app.schemas import Category, Finding, Severity

_HEADERS = {
    "content-security-policy": Severity.medium,
    "strict-transport-security": Severity.medium,
    "x-content-type-options": Severity.low,
    "x-frame-options": Severity.low,
}


def run_security(html: str, headers: dict[str, str] | None = None, base_url: str = "") -> list[Finding]:
    out: list[Finding] = []

    def add(rule, sev, msg, sel=None, ev=None):
        out.append(Finding(source="security", category=Category.security, severity=sev,
                           rule_id=rule, message=msg, selector=sel, evidence=ev))

    if headers is not None:
        low = {k.lower(): v for k, v in headers.items()}
        for h, sev in _HEADERS.items():
            framed = h == "x-frame-options" and "frame-ancestors" in low.get("content-security-policy", "")
            if h not in low and not framed:
                add("missing-header", sev, f"Missing security header: {h}", ev=h)
        for k, c in headers.items():
            if k.lower() == "set-cookie":
                for flag in ("httponly", "secure"):
                    if flag not in c.lower():
                        add("cookie-flag", Severity.medium, f"Cookie missing {flag}", ev=c[:80])

    soup = BeautifulSoup(html, "lxml")
    https = base_url.startswith("https://")
    for el in soup.find_all(True):
        sel = el.name + (f"#{el['id']}" if el.get("id") else "")
        for attr in el.attrs:
            if attr.startswith("on"):
                add("inline-handler", Severity.low, f"Inline event handler '{attr}' (CSP-unfriendly, XSS risk)",
                    sel, str(el)[:120])
        if el.name == "a" and el.get("target") == "_blank" and "noopener" not in (el.get("rel") or []):
            add("blank-no-noopener", Severity.medium, "target=_blank without rel=noopener", sel, str(el)[:120])
        for attr in ("src", "href", "action"):
            v = el.get(attr) or ""
            if v.startswith("http://") and (https or el.name == "form"):
                add("insecure-url", Severity.high if el.name == "form" else Severity.medium,
                    f"Insecure http:// URL in <{el.name} {attr}>", sel, v)
        if el.name == "form" and (el.get("method") or "get").lower() == "get" \
                and el.find("input", {"type": "password"}):
            add("password-in-get", Severity.critical, "Form with password field uses GET", sel)
        if el.name == "input" and el.get("type") == "password" and el.get("autocomplete") is None:
            add("password-autocomplete", Severity.low, "Password input has no autocomplete attribute", sel)
    return out
