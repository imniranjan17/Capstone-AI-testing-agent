from __future__ import annotations

from app.schemas import Report


def to_json(report: dict | Report) -> dict:
    data = report.model_dump(mode="json") if isinstance(report, Report) else dict(report)
    if data.get("retrieval_debug") is None:
        data["retrieval_debug"] = None
    return data
