"""Typed request/response contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

SCOPE_LIMITATION = (
    "This verdict applies only to the supplied input and checks executed. It is not a "
    "declaration of complete WCAG conformance for the page, application, or website."
)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class OverallVerdict(str, Enum):
    FAIL = "FAIL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PASS_WITH_SCOPE_LIMITATION = "PASS_WITH_SCOPE_LIMITATION"


class HtmlRequest(BaseModel):
    input_type: Literal["html"]
    target_standard: str = "WCAG_2_2_AA"
    content: str


class AxeReportRequest(BaseModel):
    input_type: Literal["axe_report"]
    target_standard: str = "WCAG_2_2_AA"
    content: dict[str, Any]


class GenericReportRequest(BaseModel):
    input_type: Literal["report"]
    target_standard: str = "WCAG_2_2_AA"
    content: dict[str, Any]


AnalyzeRequest = Union[HtmlRequest, AxeReportRequest, GenericReportRequest]


class Observation(BaseModel):
    """A normalized, deterministic or report-sourced observation."""

    rule_id: str
    status: Literal["fail", "pass", "manual", "unknown"]
    impact: Optional[str] = None
    element: str = ""
    selector: str = ""
    observation: str
    source: Literal["dom_check", "axe_report", "report"] = "dom_check"
    candidate_criteria: list[str] = Field(default_factory=list)


class WcagRef(BaseModel):
    criterion: str
    title: str
    level: str
    source_title: str
    source_url: str
    evidence_excerpt: str
    authority: str = "normative"


class Finding(BaseModel):
    finding_id: str
    verdict: Verdict
    rule_id: str
    impact: Optional[str] = None
    element: str = ""
    selector: str = ""
    observation: str
    wcag: list[WcagRef] = Field(default_factory=list)
    reason: str = ""
    recommendation: str = ""
    confidence: float = 0.0
    evidence_types: list[str] = Field(default_factory=list)
    requires_human_review: bool = False


class Scope(BaseModel):
    input_type: str
    elements_evaluated: int
    automated_checks_executed: int
    limitation: str = SCOPE_LIMITATION


class Summary(BaseModel):
    failed: int = 0
    passed: int = 0
    manual_review: int = 0
    insufficient_evidence: int = 0


class Report(BaseModel):
    run_id: str
    target_standard: str
    overall_verdict: OverallVerdict
    scope: Scope
    summary: Summary
    findings: list[Finding]
    manual_review_items: list[Finding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    retrieval_debug: Optional[dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LlmExplanation(BaseModel):
    """Schema the LLM must return per finding. It cannot change verdicts."""

    reason: str
    recommendation: str
    criteria: list[str] = Field(default_factory=list)
