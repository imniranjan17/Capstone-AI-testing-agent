import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="wcag-tests-")
os.environ["SQLITE_PATH"] = str(Path(_tmp) / "agent.db")
os.environ["RETRIEVAL_ENABLED"] = "false"  # unit/integration tests use BM25 only; no model downloads
os.environ["GROQ_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""

import pytest  # noqa: E402

from app.config import ROOT, get_settings  # noqa: E402


@pytest.fixture(scope="session")
def retriever():
    from app.knowledge import loader
    from app.retrieval.service import Retriever

    get_settings.cache_clear()
    loader.ingest_paths(loader.discover(ROOT / "knowledge"))
    return Retriever(loader.load_chunks())


class FakeLLM:
    """Returns a canned explanation citing whatever criteria the evidence contains, plus a bogus one."""

    def __init__(self, reply: str | None = None):
        self.calls = 0
        self.reply = reply

    def chat(self, messages):
        import json

        self.calls += 1
        if self.reply is not None:
            return self.reply
        user = json.loads(messages[-1]["content"]) if messages[-1]["role"] == "user" and messages[-1]["content"].startswith("{") else {}
        ids = [p["criterion"] for p in user.get("retrieved_evidence", [])][:1] + ["9.9.9"]
        return json.dumps({"reason": "Because evidence.", "recommendation": "Fix it.", "criteria": ids})


@pytest.fixture
def graph(retriever):
    from app.agent.graph import build_graph

    return build_graph(retriever, None)
