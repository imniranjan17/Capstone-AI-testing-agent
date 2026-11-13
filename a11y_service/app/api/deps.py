from __future__ import annotations

import threading
from typing import Any

from app.agent.graph import build_graph
from app.evaluation.evaluator import default_client
from app.retrieval.service import get_retriever

_lock = threading.Lock()
_graph: Any | None = None


def get_graph() -> Any:
    global _graph
    with _lock:
        if _graph is None:
            _graph = build_graph(get_retriever(), default_client())
        return _graph


def set_graph(graph: Any | None) -> None:
    global _graph
    with _lock:
        _graph = graph
