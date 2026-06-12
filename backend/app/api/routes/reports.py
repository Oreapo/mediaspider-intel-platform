from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..dependencies import ANALYST_ROLES, READ_ROLES, get_audit_service, get_report_service, require_roles, require_user
from ..schemas.report import ReportGenerateRequest, ReportUpdateRequest
from ...application.audit_service import AuditService
from ...application.auth_service import AuthUser
from ...application.report_service import ReportService


router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("")
def list_reports(
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ReportService = Depends(get_report_service),
):
    reports, total = service.list_reports_page(limit=limit, offset=offset)
    return {"reports": [report.model_dump(mode="json") for report in reports], "total": total}


@router.post("", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def generate_report(
    payload: ReportGenerateRequest,
    service: ReportService = Depends(get_report_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    try:
        report = service.generate_report(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="report.generate",
        actor=actor,
        target_type="report",
        target_id=report.id,
        summary=f"生成报告：{report.report_name}",
        metadata_json={"case_id": report.case_id, "report_type": report.report_type.value, "storage_uri": report.storage_uri},
    )
    return {"message": "Report generated", "report": report.model_dump(mode="json")}


@router.get("/{report_id}")
def get_report(report_id: str, service: ReportService = Depends(get_report_service)):
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report": report.model_dump(mode="json")}


@router.patch("/{report_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def update_report(
    report_id: str,
    payload: ReportUpdateRequest,
    service: ReportService = Depends(get_report_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    try:
        report = service.update_report(report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="report.update",
        actor=actor,
        target_type="report",
        target_id=report.id,
        summary=f"更新报告：{report.report_name}",
        metadata_json={"fields": sorted(payload.model_dump(exclude_unset=True).keys()), "case_id": report.case_id},
    )
    return {"message": "Report updated", "report": report.model_dump(mode="json")}


@router.delete("/{report_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def delete_report(
    report_id: str,
    delete_storage: bool = Query(False),
    service: ReportService = Depends(get_report_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    report = service.get_report(report_id)
    deleted = service.delete_report(report_id, delete_storage=delete_storage)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    audit_service.record(
        action="report.delete",
        actor=actor,
        target_type="report",
        target_id=report_id,
        summary=f"删除报告：{report.report_name if report else report_id}",
        metadata_json={"delete_storage": delete_storage, "case_id": report.case_id if report else ""},
    )
    return {"message": "Report deleted"}


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    service: ReportService = Depends(get_report_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_user),
):
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    path = service.resolve_report_path(report.storage_uri)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    audit_service.record(
        action="report.download",
        actor=actor,
        target_type="report",
        target_id=report.id,
        summary=f"下载报告：{report.report_name}",
        metadata_json={"case_id": report.case_id, "storage_uri": report.storage_uri},
    )
    return FileResponse(path, filename=f"{report.report_name}.md", media_type="text/markdown")
