from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Category(str, Enum):
    accessibility = "accessibility"
    validation = "validation"
    links = "links"
    security = "security"
    functional = "functional"  # MCP automation tests


class Decision(str, Enum):
    auto_suggest = "auto_suggest"   # guideline-backed patch, no human needed
    needs_human = "needs_human"     # route to review queue
    none = "none"


class Finding(BaseModel):
    source: str                      # "a11y" | "validation" | "links" | "security" | "mcp"
    category: Category
    severity: Severity = Severity.medium
    rule_id: str
    message: str
    selector: str | None = None
    evidence: str | None = None
    # filled by the decision step
    decision: Decision = Decision.none
    decision_reason: str | None = None
    suggested_fix: str | None = None
    review_status: str = "n/a"       # n/a | pending | approved | rejected


class SnapshotResult(BaseModel):
    status: str                      # baseline | changed | unchanged
    diff: str = ""
    findings: list[Finding] = Field(default_factory=list)
