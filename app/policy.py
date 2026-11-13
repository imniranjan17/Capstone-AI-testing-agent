"""Step 7: deterministic decision policy. The LLM (see patches.py) only drafts text, never decides."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel

from app.schemas import Category, Decision, Finding, Severity

GUIDELINES_DIR = Path(__file__).resolve().parent.parent / "guidelines"
_ORDER = {Severity.low: 0, Severity.medium: 1, Severity.high: 2, Severity.critical: 3}


class Guideline(BaseModel):
    id: str
    rule_ids: list[str]
    auto_suggest: bool = False
    risk: str = "medium"
    max_severity: Severity = Severity.medium
    fix: str


def load_guidelines(directory: Path | str = GUIDELINES_DIR) -> dict[str, Guideline]:
    """rule_id -> Guideline"""
    out: dict[str, Guideline] = {}
    for p in sorted(Path(directory).glob("*.yaml")):
        for g in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("guidelines", []):
            gl = Guideline(**g)
            for r in gl.rule_ids:
                out[r] = gl
    return out


def decide_one(f: Finding, guidelines: dict[str, Guideline], mcp_selectors: set[str]) -> tuple[Decision, str, Guideline | None]:
    g = guidelines.get(f.rule_id)
    if f.category == Category.security:
        return Decision.needs_human, "security findings always need human review", g
    if f.category == Category.functional:
        return Decision.needs_human, "failed automation test needs human review", g
    if g is None:
        return Decision.needs_human, "no guideline matches this rule", None
    if not g.auto_suggest:
        return Decision.needs_human, f"guideline '{g.id}' requires human judgement", g
    if g.risk != "low":
        return Decision.needs_human, f"guideline '{g.id}' risk is {g.risk}", g
    if _ORDER[f.severity] > _ORDER[g.max_severity]:
        return Decision.needs_human, f"severity {f.severity.value} exceeds guideline limit {g.max_severity.value}", g
    if f.selector and f.selector in mcp_selectors:
        return Decision.needs_human, "related automation test failure on same element", g
    return Decision.auto_suggest, f"guideline '{g.id}' is low-risk and auto-approved", g


def make_decider(guidelines: dict[str, Guideline] | None = None,
                 drafter: Callable[[Finding, Guideline], str] | None = None):
    """Returns decide(findings) -> findings, for use as the graph's decide step."""
    gl = guidelines if guidelines is not None else load_guidelines()

    def decide(findings: list[Finding]) -> list[Finding]:
        mcp_sel = {f.selector for f in findings if f.source == "mcp" and f.selector}
        out = []
        for f in findings:
            d, reason, g = decide_one(f, gl, mcp_sel)
            upd = {"decision": d, "decision_reason": reason,
                   "review_status": "pending" if d == Decision.needs_human else "n/a"}
            if g is not None:
                upd["suggested_fix"] = drafter(f, g) if (drafter and d == Decision.auto_suggest) else g.fix
            out.append(f.model_copy(update=upd))
        return out

    return decide
