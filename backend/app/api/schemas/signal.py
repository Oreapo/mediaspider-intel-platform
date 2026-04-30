from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...domain.models.signal import RiskLevel, SignalStatus, SignalType


class SignalCreateRequest(BaseModel):
    dataset_id: str = Field(min_length=1)
    task_run_id: str | None = None
    signal_type: SignalType = SignalType.MANUAL
    signal_source: str = Field(default="manual", min_length=1, max_length=80)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = Field(default=50, ge=0, le=100)
    summary: str = Field(min_length=1, max_length=500)
    payload_json: dict[str, Any] = Field(default_factory=dict)
    status: SignalStatus = SignalStatus.NEW


class SignalStatusUpdateRequest(BaseModel):
    status: SignalStatus


class SignalExtractionRequest(BaseModel):
    dataset_id: str = Field(min_length=1)
    extractors: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=200)
