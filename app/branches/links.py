"""Step 4b: broken link check."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.schemas import Category, Finding, Severity


def check_url(url: str, timeout: float = 8.0) -> int | str:
    """Return HTTP status or an error string. HEAD first, GET fallback."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                          headers={"User-Agent": "web-testing-agent/0.1"}) as c:
            r = c.head(url)
            if r.status_code in (403, 405, 501):
                r = c.get(url)
            return r.status_code
    except httpx.HTTPError as e:
        return e.__class__.__name__


def run_links(html: str, base_url: str = "", checker: Callable[[str], int | str] = check_url,
              max_links: int = 50, workers: int = 8) -> list[Finding]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Finding] = []
    targets: dict[str, str] = {}  # url -> selector
    for a in soup.find_all(["a", "img", "link", "script"]):
        attr = "href" if a.name in ("a", "link") else "src"
        v = (a.get(attr) or "").strip()
        sel = a.name + (f"#{a['id']}" if a.get("id") else "")
        if a.name == "a" and (v in ("", "#") or v.lower().startswith("javascript:")):
            out.append(Finding(source="links", category=Category.links, severity=Severity.low,
                               rule_id="link-empty-href", message=f"Link has empty/placeholder href '{v}'",
                               selector=sel, evidence=str(a)[:160]))
            continue
        if not v or v.startswith(("mailto:", "tel:", "data:", "#")):
            continue
        full = urldefrag(urljoin(base_url, v))[0]
        if urlparse(full).scheme in ("http", "https"):
            targets.setdefault(full, sel)
    urls = list(targets)[:max_links]
    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(checker, urls))
    for u, res in zip(urls, results):
        if isinstance(res, str) or res >= 400:
            sev = Severity.high if (isinstance(res, int) and res < 500) else Severity.medium
            out.append(Finding(source="links", category=Category.links, severity=sev,
                               rule_id="broken-link", message=f"{u} -> {res}",
                               selector=targets[u], evidence=str(res)))
    return out
