from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.persistence.database import get_run
from app.reports.html_report import to_html

router = APIRouter(prefix="/v1", tags=["runs"])


@router.get("/runs/{run_id}")
def read_run(run_id: str, format: str = Query("json", pattern="^(json|html)$")):
    report = get_run(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Run not found")
    report["retrieval_debug"] = None  # debug rankings are never served from storage
    if format == "html":
        return HTMLResponse(to_html(report))
    return report
