from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import OPERATOR_ROLES, READ_ROLES, get_platform_profile_service, require_roles
from ..schemas.platform import PlatformProfileCreateRequest, PlatformProfileUpdateRequest, PlatformTaskModelResponse
from ...application.platform_profile_service import PlatformProfileService
from ...domain.models.platform import PlatformKey
from ...services.platform_task_model_service import platform_task_model_service

router = APIRouter(prefix="/platforms", tags=["platforms"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("", response_model=list[PlatformTaskModelResponse])
def list_platform_task_models():
    return platform_task_model_service.list_models()


@router.get("/profiles")
def list_platform_profiles(
    platform: PlatformKey | None = None,
    service: PlatformProfileService = Depends(get_platform_profile_service),
):
    return {"profiles": [service.sanitize_profile(profile) for profile in service.list_profiles(platform)]}


@router.post("/profiles", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def create_platform_profile(
    payload: PlatformProfileCreateRequest,
    service: PlatformProfileService = Depends(get_platform_profile_service),
):
    profile = service.create_profile(payload)
    return {"message": "Platform profile created", "profile": service.sanitize_profile(profile)}


@router.get("/profiles/{profile_id}")
def get_platform_profile(
    profile_id: str,
    service: PlatformProfileService = Depends(get_platform_profile_service),
):
    profile = service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Platform profile not found")
    return {"profile": service.sanitize_profile(profile)}


@router.patch("/profiles/{profile_id}", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def update_platform_profile(
    profile_id: str,
    payload: PlatformProfileUpdateRequest,
    service: PlatformProfileService = Depends(get_platform_profile_service),
):
    try:
        profile = service.update_profile(profile_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Platform profile updated", "profile": service.sanitize_profile(profile)}


@router.delete("/profiles/{profile_id}", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def delete_platform_profile(
    profile_id: str,
    service: PlatformProfileService = Depends(get_platform_profile_service),
):
    deleted = service.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Platform profile not found")
    return {"message": "Platform profile deleted"}


@router.get("/profiles/{profile_id}/diagnostics")
def diagnose_platform_profile(
    profile_id: str,
    service: PlatformProfileService = Depends(get_platform_profile_service),
):
    try:
        return {"diagnostics": service.diagnose_profile(profile_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{platform}", response_model=PlatformTaskModelResponse)
def get_platform_task_model(platform: str):
    for model in platform_task_model_service.list_models():
        if model.platform == platform:
            return model
    raise HTTPException(status_code=404, detail="Platform model not found")
