"""Best-effort, static HTML parsing. Never executes scripts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag
from lxml import etree

_SENSITIVE_INPUT_TYPES = {"password", "hidden"}
_SENSITIVE_ATTR = re.compile(r"(token|secret|auth|session|csrf|password|cookie)", re.I)


@dataclass
class ParsedDocument:
    soup: BeautifulSoup
    is_full_document: bool
    warnings: list[str] = field(default_factory=list)


def parse_html(content: str) -> ParsedDocument:
    warnings: list[str] = []
    lowered = content.lower()
    is_full = "<html" in lowered
    try:
        parser = etree.HTMLParser(recover=True)
        etree.fromstring(content.encode("utf-8", "ignore") or b"<div/>", parser)
        for err in parser.error_log:
            msg = err.message or ""
            if "mismatch" in msg or "unexpected end tag" in msg or "Unexpected end tag" in msg:
                warnings.append(f"Malformed HTML (line {err.line}): {msg}")
    except Exception as exc:  # pragma: no cover - lxml is very tolerant
        warnings.append(f"HTML parse warning: {exc}")
    soup = BeautifulSoup(content, "lxml")
    return ParsedDocument(soup=soup, is_full_document=is_full, warnings=warnings[:10])


def selector_for(tag: Tag) -> str:
    """Short structural CSS path (stops at an id or at body/html)."""
    parts: list[str] = []
    node: Tag | None = tag
    while node is not None and node.name not in (None, "[document]", "html", "body"):
        if node.get("id"):
            parts.append(f"{node.name}#{node['id']}")
            break
        siblings = [s for s in node.parent.find_all(node.name, recursive=False)] if node.parent else [node]
        idx = next((i for i, s in enumerate(siblings, 1) if s is node), 1)
        parts.append(f"{node.name}:nth-of-type({idx})")
        node = node.parent if isinstance(node.parent, Tag) else None
    return " > ".join(reversed(parts)) or tag.name


def excerpt(tag: Tag, limit: int = 300) -> str:
    """Element HTML with sensitive values redacted and length capped."""
    clone = BeautifulSoup(str(tag), "lxml")
    el = clone.find(tag.name)
    if el is None:
        return str(tag)[:limit]
    for node in [el, *el.find_all(True)]:
        itype = (node.get("type") or "").lower() if node.name == "input" else ""
        if node.name == "input" and "value" in node.attrs and (
            itype in _SENSITIVE_INPUT_TYPES or itype == "" or itype in {"text", "email", "tel", "search"}
        ):
            node["value"] = "[REDACTED]"
        for attr in list(node.attrs):
            if _SENSITIVE_ATTR.search(attr) and attr not in {"aria-label"}:
                node[attr] = "[REDACTED]"
    text = str(el)
    return text if len(text) <= limit else text[: limit - 3] + "..."
