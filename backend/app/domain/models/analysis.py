from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id


class AnalysisScope(str, Enum):
    COMMON = "common"
    PLATFORM = "platform"
    CROSS_PLATFORM = "cross_platform"


class AnalysisJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AnalysisJob(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("aj"))
    dataset_id: str
    analysis_scope: AnalysisScope
    analysis_type: str
    status: AnalysisJobStatus = AnalysisJobStatus.PENDING
    parameters_json: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str = ""


class AnalysisOutput(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("ao"))
    analysis_job_id: str
    output_type: str
    title: str
    summary: str = ""
    payload_json: dict[str, Any] = Field(default_factory=dict)


class InsightReport(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("rpt"))
    report_name: str
    report_type: str
    dataset_ids: list[str] = Field(default_factory=list)
    analysis_job_ids: list[str] = Field(default_factory=list)
    report_payload_json: dict[str, Any] = Field(default_factory=dict)
