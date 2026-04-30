from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_analysis_service
from ..schemas.analysis import AnalysisJobCreateRequest
from ...application.analysis_service import AnalysisService


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/jobs")
def list_analysis_jobs(service: AnalysisService = Depends(get_analysis_service)):
    return {"jobs": [job.model_dump(mode="json") for job in service.list_jobs()]}


@router.post("/jobs")
def create_analysis_job(
    payload: AnalysisJobCreateRequest,
    service: AnalysisService = Depends(get_analysis_service),
):
    try:
        job = service.create_job(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Analysis job created", "job": job.model_dump(mode="json")}


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
