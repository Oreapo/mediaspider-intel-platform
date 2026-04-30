from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_case_service
from ..schemas.case import CaseCreateRequest, CaseLinkCreateRequest, CaseNoteCreateRequest, CaseUpdateRequest
from ...application.case_service import CaseService


router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
def list_cases(service: CaseService = Depends(get_case_service)):
    return {"cases": [case.model_dump(mode="json") for case in service.list_cases()]}


@router.post("")
def create_case(payload: CaseCreateRequest, service: CaseService = Depends(get_case_service)):
    case = service.create_case(payload)
    return {"message": "Case created", "case": case.model_dump(mode="json")}


@router.get("/{case_id}")
def get_case_detail(case_id: str, service: CaseService = Depends(get_case_service)):
    detail = service.get_case_detail(case_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return detail


@router.patch("/{case_id}")
def update_case(
    case_id: str,
    payload: CaseUpdateRequest,
    service: CaseService = Depends(get_case_service),
):
    try:
        case = service.update_case(case_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Case updated", "case": case.model_dump(mode="json")}


@router.delete("/{case_id}")
def delete_case(case_id: str, service: CaseService = Depends(get_case_service)):
    deleted = service.delete_case(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"message": "Case deleted"}


@router.post("/{case_id}/links")
def add_case_link(
    case_id: str,
    payload: CaseLinkCreateRequest,
    service: CaseService = Depends(get_case_service),
):
    try:
        link = service.add_link(case_id=case_id, **payload.model_dump())
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"message": "Case link added", "link": link.model_dump(mode="json")}


@router.delete("/links/{link_id}")
def delete_case_link(link_id: str, service: CaseService = Depends(get_case_service)):
    deleted = service.delete_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case link not found")
    return {"message": "Case link deleted"}


@router.post("/{case_id}/notes")
def add_case_note(
    case_id: str,
    payload: CaseNoteCreateRequest,
    service: CaseService = Depends(get_case_service),
):
    try:
        note = service.add_note(case_id=case_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Case note added", "note": note.model_dump(mode="json")}


@router.delete("/notes/{note_id}")
def delete_case_note(note_id: str, service: CaseService = Depends(get_case_service)):
    deleted = service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case note not found")
    return {"message": "Case note deleted"}


@router.get("/{case_id}/timeline")
def get_case_timeline(case_id: str, service: CaseService = Depends(get_case_service)):
    try:
        return {"timeline": service.build_timeline(case_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
