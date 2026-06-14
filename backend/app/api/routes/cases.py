from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import ANALYST_ROLES, READ_ROLES, get_audit_service, get_case_service, require_roles
from ..schemas.case import CaseCreateRequest, CaseLinkCreateRequest, CaseNoteCreateRequest, CaseUpdateRequest
from ...application.audit_service import AuditService
from ...application.auth_service import AuthUser
from ...application.case_service import CaseService
from ...domain.models.audit import AuditEvent
from ...domain.models.case import Case
from ...domain.models.case import CasePriority, CaseStatus


router = APIRouter(prefix="/cases", tags=["cases"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("")
def list_cases(
    status: CaseStatus | None = None,
    priority: CasePriority | None = None,
    case_type: str = "",
    owner: str = "",
    q: str = "",
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CaseService = Depends(get_case_service),
):
    cases, total = service.list_cases_page(
        status=status,
        priority=priority,
        case_type=case_type,
        owner=owner,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {"cases": [case.model_dump(mode="json") for case in cases], "total": total}


@router.post("", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def create_case(
    payload: CaseCreateRequest,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    case = service.create_case(payload)
    audit_service.record(
        action="case.create",
        actor=actor,
        target_type="case",
        target_id=case.id,
        summary=f"创建案件：{case.case_name}",
        metadata_json={
            "case_type": case.case_type,
            "priority": case.priority.value,
            "previous_status": None,
            "new_status": case.status.value,
            "status_changed": True,
        },
    )
    return {"message": "Case created", "case": case.model_dump(mode="json")}


@router.get("/{case_id}")
def get_case_detail(
    case_id: str,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    detail = service.get_case_detail(case_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Case not found")
    audit_events = audit_service.list_events(target_type="case", target_id=case_id)
    status_history = _build_case_status_history(detail["case"], audit_events)
    detail["timeline"] = _merge_case_status_timeline(detail["timeline"], status_history)
    detail["status_history"] = status_history
    detail["audit_events"] = [event.model_dump(mode="json") for event in audit_events[:100]]
    return detail


@router.patch("/{case_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def update_case(
    case_id: str,
    payload: CaseUpdateRequest,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    previous_case = service.get_case(case_id)
    try:
        case = service.update_case(case_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    changed_fields = sorted(payload.model_dump(exclude_unset=True).keys())
    metadata_json: dict[str, Any] = {"fields": changed_fields}
    if payload.status is not None and previous_case is not None:
        previous_status = previous_case.status.value
        new_status = case.status.value
        metadata_json.update(
            {
                "previous_status": previous_status,
                "new_status": new_status,
                "status_changed": previous_status != new_status,
            }
        )
    audit_service.record(
        action="case.update",
        actor=actor,
        target_type="case",
        target_id=case.id,
        summary=f"更新案件：{case.case_name}",
        metadata_json=metadata_json,
    )
    return {"message": "Case updated", "case": case.model_dump(mode="json")}


@router.delete("/{case_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def delete_case(
    case_id: str,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    case = service.get_case(case_id)
    deleted = service.delete_case(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")
    audit_service.record(
        action="case.delete",
        actor=actor,
        target_type="case",
        target_id=case_id,
        summary=f"删除案件：{case.case_name if case else case_id}",
        metadata_json={"case_name": case.case_name if case else ""},
    )
    return {"message": "Case deleted"}


@router.post("/{case_id}/links", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def add_case_link(
    case_id: str,
    payload: CaseLinkCreateRequest,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    try:
        link = service.add_link(case_id=case_id, **payload.model_dump())
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    audit_service.record(
        action="case.link.add",
        actor=actor,
        target_type="case",
        target_id=case_id,
        summary=f"案件挂接对象：{payload.link_type.value} / {payload.target_id}",
        metadata_json={"case_link_id": link.id, "link_type": payload.link_type.value, "linked_target_id": payload.target_id},
    )
    return {"message": "Case link added", "link": link.model_dump(mode="json")}


@router.delete("/links/{link_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def delete_case_link(
    link_id: str,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    deleted = service.delete_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case link not found")
    audit_service.record(
        action="case.link.delete",
        actor=actor,
        target_type="case_link",
        target_id=link_id,
        summary=f"删除案件挂接：{link_id}",
    )
    return {"message": "Case link deleted"}


@router.post("/{case_id}/notes", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def add_case_note(
    case_id: str,
    payload: CaseNoteCreateRequest,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    try:
        note = service.add_note(case_id=case_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="case.note.add",
        actor=actor,
        target_type="case",
        target_id=case_id,
        summary=f"案件新增备注：{note.body[:80]}",
        metadata_json={"case_note_id": note.id, "note_type": note.note_type},
    )
    return {"message": "Case note added", "note": note.model_dump(mode="json")}


@router.delete("/notes/{note_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def delete_case_note(
    note_id: str,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    deleted = service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case note not found")
    audit_service.record(
        action="case.note.delete",
        actor=actor,
        target_type="case_note",
        target_id=note_id,
        summary=f"删除案件备注：{note_id}",
    )
    return {"message": "Case note deleted"}


@router.get("/{case_id}/timeline")
def get_case_timeline(
    case_id: str,
    service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    try:
        timeline = service.build_timeline(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    case = service.get_case(case_id)
    audit_events = audit_service.list_events(target_type="case", target_id=case_id)
    status_history = _build_case_status_history(case, audit_events) if case is not None else []
    return {"timeline": _merge_case_status_timeline(timeline, status_history)}


def _build_case_status_history(
    case: Case | dict[str, Any],
    audit_events: list[AuditEvent],
) -> list[dict[str, Any]]:
    case_payload = case.model_dump(mode="json") if isinstance(case, Case) else case
    history: list[dict[str, Any]] = []
    create_event: AuditEvent | None = None

    for event in sorted(audit_events, key=lambda item: (item.created_at, item.id)):
        metadata = event.metadata_json
        if event.action == "case.create":
            create_event = event
            continue
        if event.action != "case.update":
            continue
        previous_status = metadata.get("previous_status")
        new_status = metadata.get("new_status")
        if not isinstance(previous_status, str) or not isinstance(new_status, str):
            continue
        if previous_status == new_status or metadata.get("status_changed") is False:
            continue
        history.append(
            {
                "previous_status": previous_status,
                "new_status": new_status,
                "changed_at": event.created_at.isoformat(),
                "actor_username": event.actor_username,
                "actor_role": event.actor_role,
                "source_event_id": event.id,
            }
        )

    initial_status = (
        history[0]["previous_status"]
        if history
        else str(case_payload.get("status") or CaseStatus.OPEN.value)
    )
    create_metadata = create_event.metadata_json if create_event is not None else {}
    recorded_initial_status = create_metadata.get("new_status")
    if isinstance(recorded_initial_status, str):
        initial_status = recorded_initial_status
    history.insert(
        0,
        {
            "previous_status": None,
            "new_status": initial_status,
            "changed_at": (
                create_event.created_at.isoformat()
                if create_event is not None
                else str(case_payload.get("created_at") or "")
            ),
            "actor_username": create_event.actor_username if create_event is not None else "",
            "actor_role": create_event.actor_role if create_event is not None else "",
            "source_event_id": create_event.id if create_event is not None else "",
        },
    )
    return history


def _merge_case_status_timeline(
    timeline: list[dict[str, Any]],
    status_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(timeline)
    for item in status_history:
        previous_status = item.get("previous_status")
        if not previous_status:
            continue
        new_status = str(item.get("new_status") or "")
        merged.append(
            {
                "event_type": "case_status_changed",
                "event_time": str(item.get("changed_at") or ""),
                "target_type": "case",
                "target_id": str(item.get("source_event_id") or ""),
                "title": f"{previous_status} -> {new_status}",
                "source_ref": {
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "actor_username": item.get("actor_username") or "",
                    "audit_event_id": item.get("source_event_id") or "",
                },
            }
        )
    return sorted(
        merged,
        key=lambda item: (item["event_time"], item["event_type"], item["target_id"]),
    )
