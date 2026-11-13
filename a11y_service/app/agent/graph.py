from __future__ import annotations

import uuid
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.pipeline import make_nodes
from app.agent.state import AccessibilityAgentState
from app.evaluation.evaluator import ChatClient
from app.retrieval.service import Retriever

ORDER = [
    "validate_input", "parse_input", "run_deterministic_checks", "normalize_observations",
    "build_retrieval_queries", "retrieve_bm25", "retrieve_dense", "fuse_rrf", "rerank_candidates",
    "evaluate_evidence", "apply_verdict_policy", "generate_report", "persist_run",
]


def build_graph(retriever: Retriever, llm: ChatClient | None):
    nodes = make_nodes(retriever, llm)
    g = StateGraph(AccessibilityAgentState)
    for name in ORDER:
        g.add_node(name, nodes[name])
    g.add_edge(START, ORDER[0])
    for a, b in zip(ORDER, ORDER[1:]):
        g.add_edge(a, b)
    g.add_edge(ORDER[-1], END)
    return g.compile()


def run_analysis(
    graph: Any, input_type: str, content: Any, target_standard: str = "WCAG_2_2_AA", debug: bool = False,
) -> dict:
    state = graph.invoke({
        "run_id": str(uuid.uuid4()), "input_type": input_type, "target_standard": target_standard,
        "raw_input": content, "errors": [], "debug": debug,
    })
    if state.get("errors"):
        raise ValueError("; ".join(e["message"] for e in state["errors"]))
    return state["report"]
