from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import READ_ROLES, get_audit_service, get_log_service, require_roles
from ...application.audit_service import AuditService
from ...application.log_service import LogService


router = APIRouter(prefix="/logs", tags=["logs"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("/runs")
def list_run_logs(service: LogService = Depends(get_log_service)):
    return {"logs": service.list_run_logs()}


@router.get("/audit")
def list_audit_events(
    target_type: str | None = None,
    target_id: str | None = None,
    actor_username: str | None = None,
    action: str | None = None,
    q: str = "",
    created_from: str | None = None,
    created_to: str | None = None,
    limit: int | None = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AuditService = Depends(get_audit_service),
):
    events = service.list_events(
        target_type=target_type,
        target_id=target_id,
        actor_username=actor_username,
        action=action,
        query=q,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return {"events": [event.model_dump(mode="json") for event in events]}


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
