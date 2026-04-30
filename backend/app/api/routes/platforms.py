from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.platform import PlatformTaskModelResponse
from ...services.platform_task_model_service import platform_task_model_service

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.get("", response_model=list[PlatformTaskModelResponse])
def list_platform_task_models():
    return platform_task_model_service.list_models()


@router.get("/{platform}", response_model=PlatformTaskModelResponse)
def get_platform_task_model(platform: str):
    for model in platform_task_model_service.list_models():
      if model.platform == platform:
        return model
    raise HTTPException(status_code=404, detail="Platform model not found")
