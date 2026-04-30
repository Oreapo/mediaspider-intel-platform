from __future__ import annotations

from pydantic import BaseModel, Field

from ...domain.models.analysis import AnalysisScope


class AnalysisJobCreateRequest(BaseModel):
    dataset_id: str = Field(min_length=1)
    analysis_scope: AnalysisScope = AnalysisScope.COMMON
    analysis_type: str = Field(min_length=1, max_length=80)
    parameters_json: dict = Field(default_factory=dict)
