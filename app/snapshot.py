"""Step 2: fetch/accept DOM, normalize, hash, compare with previous snapshot."""
from __future__ import annotations

import difflib
import hashlib
import re
import sqlite3
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Comment

from app.config import settings
from app.schemas import SnapshotResult


def _conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, hash TEXT, html TEXT, "
              "updated TEXT DEFAULT CURRENT_TIMESTAMP)")
    return c


def fetch_html(url: str, timeout: float = 15.0) -> str:
    r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "web-testing-agent/0.1"})
    r.raise_for_status()
    return r.text


def normalize(html: str) -> str:
    """Strip volatile parts (scripts, comments, nonces, csrf tokens) and pretty-print."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "noscript"]):
        t.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for el in soup.find_all(True):
        for attr in ("nonce", "data-reactid", "data-react-checksum"):
            el.attrs.pop(attr, None)
        if el.name == "input" and "csrf" in (el.get("name") or "").lower():
            el.attrs.pop("value", None)
    text = soup.prettify()
    return re.sub(r"[ \t]+\n", "\n", text)


def digest(normalized: str) -> str:
    return hashlib.sha256(normalized.encode()).hexdigest()


def detect_change(key: str, html: str, db_path: str | None = None, save: bool = True) -> SnapshotResult:
    """key = URL or a demo name. Returns baseline/changed/unchanged (+diff)."""
    norm = normalize(html)
    h = digest(norm)
    with _conn(db_path) as c:
        row = c.execute("SELECT hash, html FROM snapshots WHERE key=?", (key,)).fetchone()
        if row is None:
            status, diff = "baseline", ""
        elif row[0] == h:
            status, diff = "unchanged", ""
        else:
            status = "changed"
            diff = "\n".join(difflib.unified_diff(row[1].splitlines(), norm.splitlines(),
                                                  "previous", "current", lineterm="", n=2))
        if save and status != "unchanged":
            c.execute("INSERT OR REPLACE INTO snapshots(key, hash, html) VALUES (?,?,?)", (key, h, norm))
    return SnapshotResult(status=status, diff=diff)
