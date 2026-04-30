from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_log_service
from ...application.log_service import LogService


router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/runs")
def list_run_logs(service: LogService = Depends(get_log_service)):
    return {"logs": service.list_run_logs()}


@router.get("/runs/{run_id}")
def get_run_log(
    run_id: str,
    max_lines: int = Query(400, ge=1, le=2000),
    service: LogService = Depends(get_log_service),
):
    try:
        return service.read_run_log(run_id, max_lines=max_lines)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
