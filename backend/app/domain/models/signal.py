from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id


class SignalType(str, Enum):
    RISK_TERM_HIT = "risk_term_hit"
    RECRUIT_PATTERN_HIT = "recruit_pattern_hit"
    SERVICE_OFFER_HIT = "service_offer_hit"
    TRAFFIC_ROUTE_HIT = "traffic_route_hit"
    CONTACT_POINT_HIT = "contact_point_hit"
    TEMPLATE_SIMILARITY_HIT = "template_similarity_hit"
    ABNORMAL_ACTIVITY_HIT = "abnormal_activity_hit"
    CROSS_PLATFORM_ALIAS_HIT = "cross_platform_alias_hit"
    SELLER_PRODUCT_CLUSTER_HIT = "seller_product_cluster_hit"
    MANUAL = "manual"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalStatus(str, Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class Signal(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("sig"))
    dataset_id: str
    task_run_id: str | None = None
    signal_type: SignalType
    signal_source: str
    risk_level: RiskLevel
    risk_score: float = Field(ge=0, le=100)
    summary: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    status: SignalStatus = SignalStatus.NEW
