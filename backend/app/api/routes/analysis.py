from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import ANALYST_ROLES, READ_ROLES, get_analysis_service, require_roles
from ..schemas.analysis import AnalysisJobCreateRequest
from ...application.analysis_service import AnalysisService


router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("/jobs")
def list_analysis_jobs(
    dataset_id: str = "",
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AnalysisService = Depends(get_analysis_service),
):
    jobs, total = service.list_jobs_page(dataset_id=dataset_id, limit=limit, offset=offset)
    return {"jobs": [job.model_dump(mode="json") for job in jobs], "total": total}


@router.post("/jobs", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def create_analysis_job(
    payload: AnalysisJobCreateRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    try:
        job = service.create_job(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Analysis job created", "job": job.model_dump(mode="json")}


@router.get("/outputs")
def list_analysis_outputs(
    job_ids: list[str] = Query(default=[]),
    service: AnalysisService = Depends(get_analysis_service),
):
    outputs = service.get_outputs_for_jobs(job_ids)
    return {"outputs": [output.model_dump(mode="json") for output in outputs]}


@router.get("/jobs/{job_id}")
def get_analysis_job(job_id: str, service: AnalysisService = Depends(get_analysis_service)):
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return {"job": job.model_dump(mode="json")}


@router.get("/jobs/{job_id}/outputs")
def get_analysis_outputs(job_id: str, service: AnalysisService = Depends(get_analysis_service)):
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return {"outputs": [output.model_dump(mode="json") for output in service.get_outputs(job_id)]}
