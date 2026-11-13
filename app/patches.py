"""Optional LLM patch drafting (Groq / any OpenAI-compatible). Never affects the decision; falls back to guideline text."""
from __future__ import annotations

import time

from app import observability as obs
from app.config import settings
from app.policy import Guideline
from app.schemas import Finding


def draft_patch(f: Finding, g: Guideline) -> str:
    if not settings.groq_api_key:
        return g.fix
    t0 = time.perf_counter()
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.groq_api_key, base_url=settings.llm_base_url, timeout=20)
        prompt = (f"Guideline: {g.fix}\nIssue: {f.message}\nElement: {f.evidence or f.selector}\n"
                  "Reply with ONLY the corrected HTML/JSX snippet for this element, no explanation. "
                  "Follow the guideline exactly; do not change anything else.")
        r = client.chat.completions.create(model=settings.llm_model, temperature=0,
                                           messages=[{"role": "user", "content": prompt}])
        text = (r.choices[0].message.content or "").strip()
        obs.record_llm("llm:patch_drafter", settings.llm_model, r.usage, (time.perf_counter() - t0) * 1000,
                       "ok" if text else "empty")
        return f"{g.fix}\n\nSuggested patch:\n{text}" if text else g.fix
    except Exception as e:
        obs.record_llm("llm:patch_drafter", settings.llm_model, None, (time.perf_counter() - t0) * 1000,
                       "error", e.__class__.__name__)
        return g.fix
