from __future__ import annotations

from fastapi import APIRouter, Body, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import Field
from typing import Annotated

from app.agent.graph import run_analysis
from app.api.deps import get_graph
from app.schemas import AnalyzeRequest, Report

router = APIRouter(prefix="/v1", tags=["analysis"])


@router.post("/analyze", response_model=Report, response_model_exclude_none=False)
async def analyze(
    request: Annotated[AnalyzeRequest, Body(discriminator="input_type")],
    debug: bool = Query(False, description="Include retrieval rankings"),
) -> Report:
    report = await run_in_threadpool(
        lambda: run_analysis(get_graph(), request.input_type, request.content, request.target_standard, debug)
    )
    return Report.model_validate(report)
