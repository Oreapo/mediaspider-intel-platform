from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...domain.models.entity import RiskEntityStatus, RiskEntityType
from ...domain.models.platform import PlatformKey


class RiskEntityCreateRequest(BaseModel):
    entity_type: RiskEntityType
    display_name: str = Field(min_length=1, max_length=160)
    platform: PlatformKey
    source_ref: dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(default=0, ge=0, le=100)
    status: RiskEntityStatus = RiskEntityStatus.ACTIVE
    profile_json: dict[str, Any] = Field(default_factory=dict)


class EntityFromSignalRequest(BaseModel):
    signal_id: str = Field(min_length=1)
    entity_type: RiskEntityType | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=160)


class EntityStatusUpdateRequest(BaseModel):
    status: RiskEntityStatus


class EntityRelationCreateRequest(BaseModel):
    source_entity_id: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)
    evidence_ref_json: dict[str, Any] = Field(default_factory=dict)


class EntityMergeRequest(BaseModel):
    source_entity_id: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    relation_type: str = Field(default="merged_alias", min_length=1, max_length=80)
    confidence: float = Field(default=0.95, ge=0, le=1)
    evidence_ref_json: dict[str, Any] = Field(default_factory=dict)
