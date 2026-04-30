from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..dependencies import get_report_service
from ..schemas.report import ReportGenerateRequest
from ...application.report_service import ReportService


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(service: ReportService = Depends(get_report_service)):
    return {"reports": [report.model_dump(mode="json") for report in service.list_reports()]}


@router.post("")
def generate_report(
    payload: ReportGenerateRequest,
    service: ReportService = Depends(get_report_service),
):
    try:
        report = service.generate_report(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Report generated", "report": report.model_dump(mode="json")}


@router.get("/{report_id}")
def get_report(report_id: str, service: ReportService = Depends(get_report_service)):
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report": report.model_dump(mode="json")}


@router.delete("/{report_id}")
def delete_report(
    report_id: str,
    delete_storage: bool = Query(False),
    service: ReportService = Depends(get_report_service),
):
    deleted = service.delete_report(report_id, delete_storage=delete_storage)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted"}


@router.get("/{report_id}/download")
def download_report(report_id: str, service: ReportService = Depends(get_report_service)):
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    path = service.resolve_report_path(report.storage_uri)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(path, filename=f"{report.report_name}.md", media_type="text/markdown")
