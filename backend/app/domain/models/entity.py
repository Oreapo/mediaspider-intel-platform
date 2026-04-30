from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id
from .platform import PlatformKey


class RiskEntityType(str, Enum):
    ACCOUNT = "account"
    SELLER = "seller"
    PRODUCT = "product"
    CONTENT = "content"
    CONTACT_POINT = "contact_point"
    ALIAS = "alias"
    UNKNOWN = "unknown"


class RiskEntityStatus(str, Enum):
    ACTIVE = "active"
    MERGED = "merged"
    DISMISSED = "dismissed"


class RiskEntity(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("ent"))
    entity_type: RiskEntityType
    display_name: str
    platform: PlatformKey
    source_ref: dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(default=0, ge=0, le=100)
    status: RiskEntityStatus = RiskEntityStatus.ACTIVE
    profile_json: dict[str, Any] = Field(default_factory=dict)


class EntityRelation(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("rel"))
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    confidence: float = Field(ge=0, le=1)
    evidence_ref_json: dict[str, Any] = Field(default_factory=dict)
