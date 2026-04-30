from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id


class ReportType(str, Enum):
    CASE_SUMMARY = "case_summary"
    EVIDENCE_REVIEW = "evidence_review"
    INVESTIGATION_BRIEF = "investigation_brief"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    ARCHIVED = "archived"


class Report(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("rpt"))
    case_id: str
    report_name: str
    report_type: ReportType = ReportType.INVESTIGATION_BRIEF
    status: ReportStatus = ReportStatus.GENERATED
    storage_uri: str = ""
    content_markdown: str = ""
    summary_json: dict[str, Any] = Field(default_factory=dict)
