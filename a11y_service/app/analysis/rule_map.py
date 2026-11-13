"""Local, versioned rule-id -> WCAG criterion mapping (tool_mapping authority)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.config import ROOT

_MAP_PATH = ROOT / "knowledge" / "mappings" / "axe_rules.json"
_TAG_RE = re.compile(r"^wcag(\d)(\d)(\d+)$")


@lru_cache
def _load() -> dict:
    return json.loads(Path(_MAP_PATH).read_text(encoding="utf-8"))


def mapping_version() -> str:
    return _load()["version"]


def candidate_criteria(rule_id: str) -> list[str]:
    return list(_load()["rules"].get(rule_id, {}).get("criteria", []))


def technical_terms(rule_id: str) -> list[str]:
    return list(_load()["rules"].get(rule_id, {}).get("terms", []))


def criteria_from_tags(tags: list[str] | None) -> list[str]:
    out: list[str] = []
    for tag in tags or []:
        m = _TAG_RE.match(tag)
        if m:
            out.append(".".join(m.groups()))
    return out
