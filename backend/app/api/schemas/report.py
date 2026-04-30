from __future__ import annotations

from pydantic import BaseModel, Field

from ...domain.models.report import ReportType


class ReportGenerateRequest(BaseModel):
    case_id: str
    report_name: str = Field(min_length=1, max_length=160)
    report_type: ReportType = ReportType.INVESTIGATION_BRIEF
