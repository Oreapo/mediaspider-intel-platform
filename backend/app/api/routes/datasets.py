from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_dataset_service
from ..schemas.dataset import DatasetCreateRequest
from ...application.dataset_service import DatasetService


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_datasets(service: DatasetService = Depends(get_dataset_service)):
    return {"datasets": [dataset.model_dump(mode="json") for dataset in service.list_datasets()]}


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, service: DatasetService = Depends(get_dataset_service)):
    dataset = service.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"dataset": dataset.model_dump(mode="json")}


@router.post("")
def create_dataset(
    payload: DatasetCreateRequest,
    service: DatasetService = Depends(get_dataset_service),
):
    dataset = service.create_dataset(**payload.model_dump())
    return {"message": "Dataset created", "dataset": dataset.model_dump(mode="json")}


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    delete_storage: bool = Query(False),
    service: DatasetService = Depends(get_dataset_service),
):
    deleted = service.delete_dataset(dataset_id, delete_storage=delete_storage)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"message": "Dataset deleted"}


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    limit: int = Query(50, ge=1, le=200),
    service: DatasetService = Depends(get_dataset_service),
):
    try:
        return service.preview_dataset(dataset_id, limit=limit)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
