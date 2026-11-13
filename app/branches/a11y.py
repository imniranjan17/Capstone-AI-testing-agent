"""Step 3: accessibility branch — delegates to the RAG-Handson WCAG agent over HTTP."""
from __future__ import annotations

import httpx

from app.config import settings
from app.schemas import Category, Finding, Severity

_IMPACT = {"minor": Severity.low, "moderate": Severity.medium,
           "serious": Severity.high, "critical": Severity.critical}


def report_to_findings(report: dict) -> list[Finding]:
    """Map a RAG-Handson Report to Findings. PASS items are skipped."""
    out: list[Finding] = []
    for f in report.get("findings", []) + report.get("manual_review_items", []):
        verdict = f.get("verdict")
        if verdict == "PASS":
            continue
        sev = _IMPACT.get(f.get("impact") or "", Severity.medium)
        if verdict == "MANUAL_REVIEW":
            sev = Severity.low
        sc = ", ".join(w["criterion"] for w in f.get("wcag", []))
        msg = f.get("observation", "")
        if f.get("recommendation"):
            msg += f" — {f['recommendation']}"
        out.append(Finding(
            source="a11y", category=Category.accessibility, severity=sev,
            rule_id=f.get("rule_id", "unknown"), message=msg,
            selector=f.get("selector") or None,
            evidence=f"verdict={verdict}; WCAG {sc}" if sc else f"verdict={verdict}",
        ))
    return out


def run_a11y(html: str, api_url: str | None = None, timeout: float = 60.0) -> list[Finding]:
    url = f"{(api_url or settings.a11y_api_url).rstrip('/')}/v1/analyze"
    try:
        r = httpx.post(url, json={"input_type": "html", "content": html}, timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPError as e:  # branch must not crash the pipeline
        return [Finding(source="a11y", category=Category.accessibility, severity=Severity.low,
                        rule_id="a11y-service-unavailable",
                        message=f"Accessibility service unavailable: {e.__class__.__name__}")]
    return report_to_findings(r.json())
