"""The 13 LangGraph nodes. `make_nodes` binds the retriever and (optional) LLM client."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.analysis import dom_checks
from app.analysis.html_parser import parse_html
from app.analysis.normalizer import normalize_axe, normalize_report
from app.config import get_settings
from app.evaluation import evaluator, policy
from app.knowledge.schemas import Chunk, RetrievalFilter
from app.persistence.database import save_run
from app.retrieval.query_builder import build_query
from app.retrieval.service import Retriever
from app.schemas import (
    SCOPE_LIMITATION, Finding, Observation, Report, Scope, Verdict, WcagRef,
)

VALID_INPUTS = {"html", "axe_report", "report"}
SUPPORTED_TARGETS = {"WCAG_2_2_AA": ("2.2", ["A", "AA"])}


def _err(stage: str, message: str) -> dict:
    return {"stage": stage, "message": message}


def _wcag_refs(criteria: list[str], pool: list[Chunk]) -> list[WcagRef]:
    refs: list[WcagRef] = []
    for sc in dict.fromkeys(criteria):
        best = next((c for c in pool if c.success_criterion == sc and c.authority == "normative"), None)
        if best:
            refs.append(WcagRef(
                criterion=sc, title=best.title, level=best.level, source_title=best.document,
                source_url=best.source_url, evidence_excerpt=best.content[:300], authority=best.authority,
            ))
    return refs


def make_nodes(retriever: Retriever, llm: evaluator.ChatClient | None) -> dict[str, Callable[[dict], dict]]:
    settings = get_settings()

    def validate_input(state: dict) -> dict:
        errors = list(state.get("errors", []))
        if state.get("input_type") not in VALID_INPUTS:
            errors.append(_err("validate_input", f"Unsupported input_type {state.get('input_type')!r}"))
        if state.get("target_standard") not in SUPPORTED_TARGETS:
            errors.append(_err("validate_input", f"Unsupported target_standard {state.get('target_standard')!r}"))
        raw = state.get("raw_input")
        if state.get("input_type") == "html" and not isinstance(raw, str):
            errors.append(_err("validate_input", "html input must be a string"))
        if state.get("input_type") in ("axe_report", "report") and not isinstance(raw, dict):
            errors.append(_err("validate_input", "report input must be a JSON object"))
        return {"errors": errors, "warnings": [], "observations": [], "evaluations": []}

    def parse_input(state: dict) -> dict:
        if state["errors"]:
            return {}
        if state["input_type"] == "html":
            doc = parse_html(state["raw_input"])
            return {"parsed_document": {"doc": doc, "is_full_document": doc.is_full_document},
                    "warnings": list(state["warnings"]) + doc.warnings}
        return {"parsed_document": {"kind": state["input_type"]}}

    def run_deterministic_checks(state: dict) -> dict:
        if state["errors"] or state["input_type"] != "html":
            return {}
        observations, executed, elements = dom_checks.run_all(state["parsed_document"]["doc"])
        return {"scope": {"checks": executed, "elements": elements, "raw_observations": observations}}

    def normalize_observations(state: dict) -> dict:
        if state["errors"]:
            return {}
        if state["input_type"] == "html":
            sc = state["scope"]
            obs, executed, elements = sc["raw_observations"], sc["checks"], sc["elements"]
        else:
            norm = (normalize_axe if state["input_type"] == "axe_report" else normalize_report)(state["raw_input"])
            obs, executed, elements = norm.observations, norm.checks_executed, norm.elements_evaluated
        return {"observations": [o.model_dump() for o in obs],
                "scope": {"checks": executed, "elements": elements}}

    def build_retrieval_queries(state: dict) -> dict:
        queries: dict[str, dict] = {}
        for i, o in enumerate(state.get("observations", [])):
            if o["status"] == "fail":
                q = build_query(Observation(**o))
                queries[str(i)] = q
        return {"retrieval_queries": [{"index": k, **v} for k, v in queries.items()]}

    flt = RetrievalFilter(document_version="2.2", levels=["A", "AA"])

    def retrieve_bm25(state: dict) -> dict:
        return {"sparse_results": {q["index"]: retriever.sparse(q["text"], flt) for q in state["retrieval_queries"]}}

    def retrieve_dense(state: dict) -> dict:
        return {"dense_results": {q["index"]: retriever.dense_search(q["text"], flt) for q in state["retrieval_queries"]}}

    def fuse_rrf(state: dict) -> dict:
        return {"fused_results": {
            q["index"]: retriever.fuse(state["sparse_results"][q["index"]], state["dense_results"][q["index"]])
            for q in state["retrieval_queries"]
        }}

    def rerank_candidates(state: dict) -> dict:
        evidence: dict[str, list[dict]] = {}
        for q in state["retrieval_queries"]:
            top = retriever.rerank(q["text"], state["fused_results"][q["index"]])
            evidence[q["index"]] = [{"chunk_id": c.chunk_id, "score": s} for c, s in top]
        return {"retrieved_evidence": evidence}

    def _evidence_for(state: dict, idx: int, obs: Observation) -> list[Chunk]:
        hits = state.get("retrieved_evidence", {}).get(str(idx))
        if hits is not None:
            return [retriever.by_id[h["chunk_id"]] for h in hits if h["chunk_id"] in retriever.by_id]
        return retriever.lookup(obs.candidate_criteria)  # manual/pass: local versioned mapping

    def evaluate_evidence(state: dict) -> dict:
        items: list[tuple[int, Observation, list[Chunk]]] = []
        for i, o in enumerate(state.get("observations", [])):
            obs = Observation(**o)
            items.append((i, obs, _evidence_for(state, i, obs)))
        warnings = list(state.get("warnings", []))

        def work(item: tuple[int, Observation, list[Chunk]]) -> dict:
            i, obs, ev = item
            res: dict[str, Any] = {"index": i, "explanation": None}
            wants_llm = obs.status == "manual" or (obs.status == "fail" and policy.supported_criteria(obs, ev))
            if llm and wants_llm and ev:
                prelim, _ = policy.finding_verdict(obs, ev)
                exp, error = evaluator.explain(llm, obs, state["target_standard"], ev, prelim.value)
                res["explanation"] = exp.model_dump() if exp else None
                res["error"] = error
            return res

        with ThreadPoolExecutor(max_workers=4) as pool:
            evals = list(pool.map(work, items))
        errs = {e["error"] for e in evals if e.get("error")}
        warnings += sorted(errs)
        if llm is None:
            warnings.append("No LLM configured (set GROQ_API_KEY): explanations omitted; deterministic results and evidence returned.")
        return {"evaluations": evals, "warnings": warnings}

    def apply_verdict_policy(state: dict) -> dict:
        findings: list[Finding] = []
        by_index = {e["index"]: e for e in state["evaluations"]}
        for i, o in enumerate(state["observations"]):
            obs = Observation(**o)
            ev = _evidence_for(state, i, obs)
            verdict, basis = policy.finding_verdict(obs, ev)
            exp = by_index.get(i, {}).get("explanation")
            supported = policy.supported_criteria(obs, ev) if obs.status == "fail" else obs.candidate_criteria
            if exp and exp["criteria"]:
                supported = [c for c in supported if c in exp["criteria"]] or supported
            refs = _wcag_refs(supported, ev) if verdict != Verdict.INSUFFICIENT_EVIDENCE else []
            types = {"fail": ["deterministic_rule"], "pass": ["deterministic_rule"], "manual": ["human_judgment_required"]}
            etypes = list(types.get(obs.status, []))
            if obs.source != "dom_check":
                etypes = ["report_evidence" if obs.status != "manual" else "human_judgment_required"]
            if refs:
                etypes.append("normative_wcag")
            confidence = {Verdict.FAIL: 0.95 if obs.source == "dom_check" else 0.85,
                          Verdict.PASS: 0.9, Verdict.MANUAL_REVIEW: 0.5,
                          Verdict.INSUFFICIENT_EVIDENCE: 0.2}[verdict]
            findings.append(Finding(
                finding_id=str(uuid.uuid4()), verdict=verdict, rule_id=obs.rule_id, impact=obs.impact,
                element=obs.element, selector=obs.selector, observation=obs.observation, wcag=refs,
                reason=(exp["reason"] if exp else basis), recommendation=(exp["recommendation"] if exp else ""),
                confidence=confidence, evidence_types=etypes,
                requires_human_review=verdict in (Verdict.MANUAL_REVIEW, Verdict.INSUFFICIENT_EVIDENCE),
            ))
        return {"evaluations": [f.model_dump(mode="json") for f in findings],
                "overall_verdict": policy.overall_verdict([f.verdict for f in findings]).value}

    def generate_report(state: dict) -> dict:
        if state["errors"]:
            return {}
        findings = [Finding(**f) for f in state["evaluations"]]
        verdicts = [f.verdict for f in findings]
        report = Report(
            run_id=state["run_id"], target_standard=state["target_standard"],
            overall_verdict=policy.overall_verdict(verdicts),
            scope=Scope(input_type=state["input_type"], elements_evaluated=state["scope"]["elements"],
                        automated_checks_executed=state["scope"]["checks"], limitation=SCOPE_LIMITATION),
            summary=policy.summarize(verdicts), findings=findings,
            manual_review_items=[f for f in findings if f.verdict == Verdict.MANUAL_REVIEW],
            warnings=list(dict.fromkeys(state.get("warnings", []))),
            retrieval_debug=_debug(state, retriever) if state.get("debug") else None,
        )
        return {"report": report.model_dump(mode="json")}

    def persist_run(state: dict) -> dict:
        if state.get("report"):
            try:
                save_run(state["report"])
            except Exception as exc:  # persistence must not break analysis
                return {"warnings": state.get("warnings", []) + [f"Run could not be persisted: {exc}"]}
        return {}

    return {
        "validate_input": validate_input, "parse_input": parse_input,
        "run_deterministic_checks": run_deterministic_checks, "normalize_observations": normalize_observations,
        "build_retrieval_queries": build_retrieval_queries, "retrieve_bm25": retrieve_bm25,
        "retrieve_dense": retrieve_dense, "fuse_rrf": fuse_rrf, "rerank_candidates": rerank_candidates,
        "evaluate_evidence": evaluate_evidence, "apply_verdict_policy": apply_verdict_policy,
        "generate_report": generate_report, "persist_run": persist_run,
    }


def _debug(state: dict, retriever: Retriever) -> dict:
    def pack(key: str) -> dict:
        return state.get(key, {})

    return {
        "stages": dict(retriever.status), "queries": state.get("retrieval_queries", []),
        "sparse": pack("sparse_results"), "dense": pack("dense_results"),
        "fused": pack("fused_results"), "reranked": pack("retrieved_evidence"),
    }
