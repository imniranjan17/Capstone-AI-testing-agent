"""Evidence-constrained LLM explanation via any OpenAI-compatible endpoint (default: Groq)."""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import ValidationError

from app.config import get_settings
from app.evaluation.prompts import REPAIR_PROMPT, SYSTEM_PROMPT
from app.knowledge.schemas import Chunk
from app.schemas import LlmExplanation, Observation

log = logging.getLogger(__name__)


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatClient:
    def __init__(self) -> None:
        from openai import OpenAI

        s = get_settings()
        self.model = s.llm_model
        self._client = OpenAI(api_key=s.effective_llm_key, base_url=s.llm_base_url, timeout=s.llm_timeout_s, max_retries=2)

    def chat(self, messages: list[dict[str, str]]) -> str:
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=0,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""


def default_client() -> ChatClient | None:
    return OpenAICompatClient() if get_settings().effective_llm_key else None


def _parse(raw: str) -> LlmExplanation:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return LlmExplanation.model_validate(json.loads(text))


def build_user_message(obs: Observation, target: str, evidence: list[Chunk], verdict: str) -> str:
    passages = [
        {"criterion": c.success_criterion, "title": c.title, "level": c.level, "authority": c.authority,
         "source": c.document, "source_url": c.source_url, "text": c.content}
        for c in evidence
    ]
    return json.dumps({
        "target_standard": target,
        "policy_verdict": verdict,
        "observation": {"rule_id": obs.rule_id, "impact": obs.impact, "message": obs.observation,
                        "element": obs.element, "selector": obs.selector, "source": obs.source},
        "retrieved_evidence": passages,
        "required_schema": {"reason": "string", "recommendation": "string", "criteria": ["string"]},
    }, ensure_ascii=False)


def explain(
    client: ChatClient, obs: Observation, target: str, evidence: list[Chunk], verdict: str,
) -> tuple[LlmExplanation | None, str | None]:
    """Returns (explanation, error). Criteria not present in the evidence are removed."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(obs, target, evidence, verdict)},
    ]
    allowed = {c.success_criterion for c in evidence}
    last_err = "unknown"
    for attempt in range(2):  # one schema-repair retry
        try:
            raw = client.chat(messages)
        except Exception as exc:
            return None, f"LLM unavailable: {exc}"
        try:
            result = _parse(raw)
            result.criteria = [c for c in result.criteria if c in allowed]
            return result, None
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_err = f"LLM returned invalid output: {exc}"
            messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": REPAIR_PROMPT}]
    return None, last_err
