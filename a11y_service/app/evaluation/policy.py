"""Deterministic verdict policy. The LLM never decides or upgrades a verdict."""
from __future__ import annotations

from app.knowledge.schemas import Chunk
from app.schemas import Observation, OverallVerdict, Summary, Verdict


def supported_criteria(obs: Observation, retrieved: list[Chunk]) -> list[str]:
    """Candidate criteria (from the rule mapping / report tags) that retrieved normative evidence backs."""
    normative = {c.success_criterion for c in retrieved if c.authority == "normative"}
    return [c for c in obs.candidate_criteria if c in normative]


def finding_verdict(obs: Observation, retrieved: list[Chunk]) -> tuple[Verdict, str]:
    """Returns (verdict, basis). `retrieved` is the evidence available for this observation."""
    if obs.status == "manual":
        return Verdict.MANUAL_REVIEW, "Requires visual, contextual, interaction or human judgment not supplied."
    if obs.status == "pass":
        return Verdict.PASS, "Only the specific executed check passed; this is not page-level conformance."
    if obs.status == "unknown":
        return Verdict.INSUFFICIENT_EVIDENCE, "The reported status could not be interpreted."
    # status == "fail"
    if not obs.candidate_criteria:
        return Verdict.INSUFFICIENT_EVIDENCE, "No WCAG criterion is mapped to this rule; similarity alone is not enough."
    if not supported_criteria(obs, retrieved):
        return Verdict.INSUFFICIENT_EVIDENCE, "No retrieved normative WCAG evidence supports the mapped criteria."
    return Verdict.FAIL, "Observed failure supported by retrieved normative WCAG evidence."


def summarize(verdicts: list[Verdict]) -> Summary:
    return Summary(
        failed=verdicts.count(Verdict.FAIL), passed=verdicts.count(Verdict.PASS),
        manual_review=verdicts.count(Verdict.MANUAL_REVIEW),
        insufficient_evidence=verdicts.count(Verdict.INSUFFICIENT_EVIDENCE),
    )


def overall_verdict(verdicts: list[Verdict]) -> OverallVerdict:
    if Verdict.FAIL in verdicts:
        return OverallVerdict.FAIL
    if Verdict.MANUAL_REVIEW in verdicts:
        return OverallVerdict.MANUAL_REVIEW
    if Verdict.INSUFFICIENT_EVIDENCE in verdicts or not verdicts:
        return OverallVerdict.INSUFFICIENT_EVIDENCE
    return OverallVerdict.PASS_WITH_SCOPE_LIMITATION
