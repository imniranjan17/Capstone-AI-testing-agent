"""Observation -> structured retrieval query. Preserves exact rule IDs and technical terms."""
from __future__ import annotations

import re
from typing import Any

from app.analysis.rule_map import technical_terms
from app.schemas import Observation

_TAG = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9-]*)")


def element_type(obs: Observation) -> str:
    m = _TAG.search(obs.element or "")
    return m.group(1).lower() if m else ""


def build_query(obs: Observation, target_standard: str = "WCAG 2.2 AA") -> dict[str, Any]:
    terms = list(dict.fromkeys([*technical_terms(obs.rule_id), obs.rule_id, element_type(obs)]))
    terms = [t for t in terms if t]
    q = {
        "rule_id": obs.rule_id,
        "element_type": element_type(obs),
        "observation": obs.observation,
        "technical_terms": terms,
        "target_standard": target_standard,
        "candidate_criteria": list(obs.candidate_criteria),
    }
    q["text"] = (
        f"{obs.rule_id}: {obs.observation} Element: {q['element_type'] or 'n/a'}. "
        f"Terms: {', '.join(terms)}. Criteria: {', '.join(obs.candidate_criteria)}."
    )
    return q
