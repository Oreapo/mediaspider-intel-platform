from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id
from .signal import RiskLevel


class NotificationEventType(str, Enum):
    SIGNAL_CREATED = "signal_created"
    CASE_UPDATED = "case_updated"
    EVIDENCE_READY = "evidence_ready"
    SCHEDULED_DIGEST = "scheduled_digest"


class NotificationChannel(str, Enum):
    WEBHOOK = "webhook"
    EMAIL = "email"
    INTERNAL_INBOX = "internal_inbox"


class NotificationDeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class NotificationRule(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("nr"))
    rule_name: str
    enabled: bool = True
    event_type: NotificationEventType = NotificationEventType.SCHEDULED_DIGEST
    risk_level_threshold: RiskLevel = RiskLevel.MEDIUM
    scenario_types: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    channels: list[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.INTERNAL_INBOX])
    cron_expr: str = "*/30 * * * *"
    cooldown_minutes: int = Field(default=60, ge=0)
    channel_config_json: dict[str, Any] = Field(default_factory=dict)
    last_executed_at: str | None = None


class NotificationDelivery(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("nd"))
    rule_id: str
    target_type: str
    target_id: str
    channel: NotificationChannel
    status: NotificationDeliveryStatus
    payload_json: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
