from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import (
    ANALYST_ROLES,
    READ_ROLES,
    get_audit_service,
    get_case_service,
    get_dataset_service,
    get_signal_service,
    get_task_service,
    require_roles,
    require_user,
)
from ..schemas.signal import SignalCreateRequest, SignalExtractionRequest, SignalStatusUpdateRequest
from ...application.audit_service import AuditService
from ...application.auth_service import AuthUser
from ...application.case_service import CaseService
from ...application.dataset_service import DatasetService
from ...application.pii import mask_clusters, mask_preview, mask_signal, mask_signals, masking_enabled
from ...application.signal_service import SignalService
from ...application.task_service import CollectionTaskService
from ...domain.models.signal import RiskLevel, SignalStatus, SignalType


router = APIRouter(prefix="/signals", tags=["signals"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("")
def list_signals(
    dataset_id: str | None = None,
    status: SignalStatus | None = None,
    risk_level: RiskLevel | None = None,
    signal_type: SignalType | None = None,
    q: str = "",
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: SignalService = Depends(get_signal_service),
):
    signals, total = service.list_signals_page(
        dataset_id=dataset_id,
        status=status,
        risk_level=risk_level,
        signal_type=signal_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    payload = [signal.model_dump(mode="json") for signal in signals]
    if masking_enabled():
        payload = mask_signals(payload)
    return {"signals": payload, "total": total}


@router.post("/extract", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def extract_signals(
    payload: SignalExtractionRequest,
    service: SignalService = Depends(get_signal_service),
):
    try:
        signals = service.extract_from_dataset(
            dataset_id=payload.dataset_id,
            extractors=payload.extractors,
            limit=payload.limit,
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    extracted = [signal.model_dump(mode="json") for signal in signals]
    if masking_enabled():
        extracted = mask_signals(extracted)
    return {
        "message": "Signals extracted",
        "signals": extracted,
        "created_count": len(signals),
        "dedupe_enabled": True,
    }


@router.get("/clusters")
def list_signal_clusters(
    dataset_id: str = Query(..., min_length=1),
    service: SignalService = Depends(get_signal_service),
):
    """Candidate gangs (团伙) — a dataset's signals grouped by shared contact point."""
    clusters = service.cluster_by_contact(dataset_id)
    if masking_enabled():
        clusters = mask_clusters(clusters)
    return {"clusters": clusters, "total": len(clusters)}


@router.get("/gangs")
def list_signal_gangs(
    dataset_id: str = Query(..., min_length=1),
    service: SignalService = Depends(get_signal_service),
):
    """Candidate gangs (团伙) linked by a relationship graph — signals joined by
    shared contact points, reused templates, or common author ids."""
    clusters = service.cluster_gangs(dataset_id)
    if masking_enabled():
        clusters = mask_clusters(clusters)
    return {"clusters": clusters, "total": len(clusters)}


@router.get("/activity")
def get_activity_bursts(
    dataset_id: str = Query(..., min_length=1),
    service: SignalService = Depends(get_signal_service),
):
    """Posting-activity timeline for a dataset with abnormal spikes flagged."""
    return service.detect_activity_bursts(dataset_id)


@router.get("/{signal_id}/detail")
def get_signal_detail(
    signal_id: str,
    service: SignalService = Depends(get_signal_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
    task_service: CollectionTaskService = Depends(get_task_service),
    case_service: CaseService = Depends(get_case_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_user),
):
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")

    dataset = dataset_service.get_dataset(signal.dataset_id)
    preview = _empty_preview()
    if dataset is not None:
        try:
            preview = dataset_service.preview_dataset(dataset.id, limit=100)
        except (FileNotFoundError, ValueError):
            preview = _empty_preview()

    source_task = None
    source_run = None
    if dataset is not None and dataset.source_task_id:
        source_task = task_service.get_task(dataset.source_task_id)
        source_run = _resolve_source_run(
            task_service,
            dataset.source_task_id,
            signal.task_run_id,
            dataset.source_run_id,
        )

    linked_case_details = _linked_case_details(signal.id, case_service)
    signal_json = signal.model_dump(mode="json")
    masked = masking_enabled()
    if masked:
        signal_json = mask_signal(signal_json)
        preview = mask_preview(preview)
    audit_service.record(
        action="signal.detail_view",
        actor=actor,
        target_type="signal",
        target_id=str(signal.id),
        summary=f"查看信号详情（{'脱敏' if masked else '明文'}）",
        metadata_json={"dataset_id": signal.dataset_id, "masked": masked},
    )
    return {
        "signal": signal_json,
        "dataset": dataset.model_dump(mode="json") if dataset else None,
        "preview": preview,
        "source_task": source_task.model_dump(mode="json") if source_task else None,
        "source_run": source_run.model_dump(mode="json") if source_run else None,
        "linked_cases": [detail["case"] for detail in linked_case_details],
        "linked_case_details": linked_case_details,
    }


@router.get("/{signal_id}")
def get_signal(signal_id: str, service: SignalService = Depends(get_signal_service)):
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal_json = signal.model_dump(mode="json")
    if masking_enabled():
        signal_json = mask_signal(signal_json)
    return {"signal": signal_json}


@router.post("", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def create_signal(
    payload: SignalCreateRequest,
    service: SignalService = Depends(get_signal_service),
):
    try:
        signal = service.create_signal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Signal created", "signal": signal.model_dump(mode="json")}


@router.patch("/{signal_id}/status", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def update_signal_status(
    signal_id: str,
    payload: SignalStatusUpdateRequest,
    service: SignalService = Depends(get_signal_service),
):
    try:
        signal = service.update_status(signal_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Signal status updated", "signal": signal.model_dump(mode="json")}


@router.delete("/{signal_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def delete_signal(signal_id: str, service: SignalService = Depends(get_signal_service)):
    deleted = service.delete_signal(signal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"message": "Signal deleted"}


def _resolve_source_run(
    task_service: CollectionTaskService,
    task_id: str,
    signal_run_id: str | None,
    dataset_run_id: str | None,
):
    wanted_ids = {item for item in [signal_run_id, dataset_run_id] if item}
    if not wanted_ids:
        return None
    return next((run for run in task_service.list_runs(task_id) if run.id in wanted_ids), None)


def _empty_preview() -> dict[str, object]:
    return {"columns": [], "rows": [], "mode": "table", "total": 0}


def _linked_case_details(signal_id: str, case_service: CaseService) -> list[dict]:
    details: list[dict] = []
    for case in case_service.list_cases():
        detail = case_service.get_case_detail(case.id)
        if detail is None:
            continue
        if any(link.get("link_type") == "signal" and link.get("target_id") == signal_id for link in detail["links"]):
            detail.setdefault("audit_events", [])
            details.append(detail)
    return details

