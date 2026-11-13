from __future__ import annotations

from typing import Any, TypedDict


class AccessibilityAgentState(TypedDict, total=False):
    run_id: str
    input_type: str
    target_standard: str
    raw_input: dict | str
    parsed_document: dict | None
    observations: list[dict]
    retrieval_queries: list[dict]
    retrieved_evidence: dict[str, list[dict]]
    evaluations: list[dict]
    overall_verdict: str | None
    errors: list[dict]
    # additions
    debug: bool
    warnings: list[str]
    scope: dict[str, Any]
    sparse_results: dict[str, list]
    dense_results: dict[str, list]
    fused_results: dict[str, list]
    report: dict | None
