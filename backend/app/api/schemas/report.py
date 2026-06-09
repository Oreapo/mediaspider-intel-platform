from __future__ import annotations

from pydantic import BaseModel, Field

from ...domain.models.report import ReportType
from ...domain.models.report import ReportStatus


class ReportGenerateRequest(BaseModel):
    case_id: str
    report_name: str = Field(min_length=1, max_length=160)
    report_type: ReportType = ReportType.INVESTIGATION_BRIEF


class ReportUpdateRequest(BaseModel):
    report_name: str | None = Field(default=None, min_length=1, max_length=160)
    status: ReportStatus | None = None
    content_markdown: str | None = None
