from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import (
    READ_ROLES,
    WORKFLOW_ROLES,
    get_analysis_service,
    get_audit_service,
    get_dataset_service,
    get_signal_service,
    require_roles,
    require_user,
)
from ..schemas.dataset import DatasetCreateRequest
from ...application.analysis_service import AnalysisService
from ...application.audit_service import AuditService
from ...application.auth_service import AuthUser
from ...application.dataset_service import DatasetService
from ...application.pii import can_reveal_pii, mask_preview, masking_enabled
from ...application.signal_service import SignalService
from ...domain.models.dataset import DatasetType
from ...domain.models.platform import PlatformKey
from ...domain.models.task import ScenarioType


router = APIRouter(prefix="/datasets", tags=["datasets"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("")
def list_datasets(
    source_platform: PlatformKey | None = None,
    dataset_type: DatasetType | None = None,
    scenario_type: ScenarioType | None = None,
    source_task_id: str = "",
    tag: str = "",
    q: str = "",
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: DatasetService = Depends(get_dataset_service),
):
    datasets, total = service.list_datasets_page(
        source_platform=source_platform,
        dataset_type=dataset_type,
        scenario_type=scenario_type,
        source_task_id=source_task_id,
        tag=tag,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {"datasets": [dataset.model_dump(mode="json") for dataset in datasets], "total": total}


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, service: DatasetService = Depends(get_dataset_service)):
    dataset = service.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"dataset": dataset.model_dump(mode="json")}


@router.post("", dependencies=[Depends(require_roles(*WORKFLOW_ROLES))])
def create_dataset(
    payload: DatasetCreateRequest,
    service: DatasetService = Depends(get_dataset_service),
):
    dataset = service.create_dataset(**payload.model_dump())
    return {"message": "Dataset created", "dataset": dataset.model_dump(mode="json")}


@router.delete("/{dataset_id}", dependencies=[Depends(require_roles(*WORKFLOW_ROLES))])
def delete_dataset(
    dataset_id: str,
    delete_storage: bool = Query(False),
    cascade: bool = Query(False),
    service: DatasetService = Depends(get_dataset_service),
    signal_service: SignalService = Depends(get_signal_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    if service.get_dataset(dataset_id) is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    related_signals = signal_service.list_signals(dataset_id=dataset_id)
    related_analysis_count = analysis_service.list_jobs_page(dataset_id=dataset_id, limit=1)[1]
    if (related_signals or related_analysis_count) and not cascade:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Dataset has linked signals or analysis jobs. Retry with cascade=true to delete them.",
                "signal_count": len(related_signals),
                "analysis_job_count": related_analysis_count,
            },
        )

    if cascade:
        signal_service.delete_signals_for_dataset(dataset_id)
        analysis_service.delete_jobs_for_dataset(dataset_id)

    deleted = service.delete_dataset(dataset_id, delete_storage=delete_storage)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {
        "message": "Dataset deleted",
        "deleted_signal_count": len(related_signals) if cascade else 0,
        "deleted_analysis_job_count": related_analysis_count if cascade else 0,
    }


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    limit: int = Query(50, ge=1, le=200),
    reveal: bool = Query(default=False),
    service: DatasetService = Depends(get_dataset_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_user),
):
    try:
        preview = service.preview_dataset(dataset_id, limit=limit)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    masked = masking_enabled()
    revealed = False
    if masked and reveal:
        if not can_reveal_pii(actor.role):
            raise HTTPException(status_code=403, detail="Not permitted to view unmasked data")
        masked = False
        revealed = True
    audit_service.record(
        action="dataset.preview",
        actor=actor,
        target_type="dataset",
        target_id=dataset_id,
        summary=f"预览数据集原始记录（{'明文' if not masked else '脱敏'}）",
        metadata_json={
            "row_count": len(preview.get("rows", [])),
            "limit": limit,
            "masked": masked,
            "revealed": revealed,
        },
    )
    return mask_preview(preview) if masked else preview
