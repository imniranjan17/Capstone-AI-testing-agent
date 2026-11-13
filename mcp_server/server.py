"""Demo MCP server exposing automation test cases as tools.

Each tool takes the page HTML and returns JSON: {"test", "passed", "details": [...]}.
Run standalone: python -m mcp_server.server  (stdio transport)
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web-test-cases")


def _result(test: str, problems: list[str]) -> str:
    return json.dumps({"test": test, "passed": not problems, "details": problems})


@mcp.tool()
def check_form_submit(html: str) -> str:
    """Every form must have a usable submit control and a non-placeholder action or JS handler."""
    soup = BeautifulSoup(html, "lxml")
    problems = []
    for i, form in enumerate(soup.find_all("form")):
        name = form.get("id") or f"form[{i}]"
        has_submit = form.find("input", attrs={"type": "submit"}) or any(
            (b.get("type") or "submit") == "submit" for b in form.find_all("button"))
        if not has_submit:
            problems.append(f"{name}: no submit control")
        action = (form.get("action") or "").strip()
        if action in ("#", "javascript:void(0)"):
            problems.append(f"{name}: placeholder action '{action}'")
    return _result("check_form_submit", problems)


@mcp.tool()
def check_nav_links(html: str) -> str:
    """Navigation links must have visible text and a real href."""
    soup = BeautifulSoup(html, "lxml")
    problems = []
    for a in soup.select("nav a, header a"):
        href = (a.get("href") or "").strip()
        label = a.get_text(strip=True) or a.get("aria-label") or ""
        if href in ("", "#") or href.lower().startswith("javascript:"):
            problems.append(f"nav link '{label or '?'}' has placeholder href '{href}'")
        if not label:
            problems.append(f"nav link {href or '?'} has no text/aria-label")
    return _result("check_nav_links", problems)


@mcp.tool()
def check_page_basics(html: str) -> str:
    """Page must have <title>, exactly one <h1>, and <html lang>."""
    soup = BeautifulSoup(html, "lxml")
    problems = []
    if not (soup.title and soup.title.get_text(strip=True)):
        problems.append("missing <title>")
    h1 = len(soup.find_all("h1"))
    if h1 != 1:
        problems.append(f"expected exactly one <h1>, found {h1}")
    if not (soup.html and soup.html.get("lang")):
        problems.append("missing <html lang>")
    return _result("check_page_basics", problems)


if __name__ == "__main__":
    mcp.run()
