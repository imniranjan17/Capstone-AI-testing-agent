"""Normalize any supported input into a list of Observations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.analysis import dom_checks
from app.analysis.html_parser import ParsedDocument, parse_html
from app.analysis.rule_map import candidate_criteria, criteria_from_tags
from app.schemas import Observation


@dataclass
class NormalizedInput:
    observations: list[Observation] = field(default_factory=list)
    checks_executed: int = 0
    elements_evaluated: int = 0
    warnings: list[str] = field(default_factory=list)


def _criteria(rule: str, tags: list[str] | None) -> list[str]:
    merged = candidate_criteria(rule) + criteria_from_tags(tags)
    return list(dict.fromkeys(merged))


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def normalize_html(content: str) -> NormalizedInput:
    return normalize_parsed(parse_html(content))


def normalize_parsed(doc: ParsedDocument) -> NormalizedInput:
    observations, executed, elements = dom_checks.run_all(doc)
    return NormalizedInput(observations, executed, elements, doc.warnings)


def normalize_axe(content: dict[str, Any]) -> NormalizedInput:
    out = NormalizedInput()
    for bucket, status in (("violations", "fail"), ("incomplete", "manual"), ("passes", "pass")):
        for rule in content.get(bucket, []) or []:
            rule_id = rule.get("id", "unknown-rule")
            crit = _criteria(rule_id, rule.get("tags"))
            nodes = rule.get("nodes") or [{}]
            out.checks_executed += 1
            if status == "pass":
                out.observations.append(Observation(
                    rule_id=rule_id, status="pass", source="axe_report", candidate_criteria=crit,
                    observation=f"axe-core reported rule '{rule_id}' as passed on {len(rule.get('nodes') or [])} node(s).",
                ))
                continue
            for node in nodes:
                out.elements_evaluated += 1
                out.observations.append(Observation(
                    rule_id=rule_id, status=status, impact=node.get("impact") or rule.get("impact"),
                    element=_text(node.get("html"))[:300], selector=_text(node.get("target")),
                    observation=rule.get("help") or rule.get("description") or f"axe rule '{rule_id}' reported an issue.",
                    source="axe_report", candidate_criteria=crit,
                ))
    return out


def normalize_report(content: dict[str, Any]) -> NormalizedInput:
    out = NormalizedInput()
    for f in content.get("findings", []) or []:
        rule_id = f.get("rule") or f.get("id") or "unknown-rule"
        raw_status = str(f.get("status", "fail")).lower()
        status = {"fail": "fail", "failed": "fail", "violation": "fail", "pass": "pass", "passed": "pass",
                  "manual": "manual", "incomplete": "manual", "needs_review": "manual"}.get(raw_status, "unknown")
        out.checks_executed += 1
        out.elements_evaluated += 1 if f.get("element") else 0
        out.observations.append(Observation(
            rule_id=rule_id, status=status, impact=f.get("impact"),
            element=_text(f.get("element"))[:300], selector=_text(f.get("selector")),
            observation=f.get("message") or f.get("description") or f"Report finding for rule '{rule_id}'.",
            source="report", candidate_criteria=_criteria(rule_id, f.get("tags")),
        ))
    return out


def normalize(input_type: str, content: Any) -> NormalizedInput:
    if input_type == "html":
        return normalize_html(content)
    if input_type == "axe_report":
        return normalize_axe(content)
    return normalize_report(content)
