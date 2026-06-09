from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...domain.models.notification import NotificationChannel, NotificationEventType
from ...domain.models.signal import RiskLevel


class NotificationRuleCreateRequest(BaseModel):
    rule_name: str = Field(min_length=1, max_length=160)
    enabled: bool = True
    event_type: NotificationEventType = NotificationEventType.SCHEDULED_DIGEST
    risk_level_threshold: RiskLevel = RiskLevel.MEDIUM
    scenario_types: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    channels: list[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.INTERNAL_INBOX])
    cron_expr: str = Field(default="*/30 * * * *", min_length=9, max_length=80)
    cooldown_minutes: int = Field(default=60, ge=0)
    channel_config_json: dict[str, Any] = Field(default_factory=dict)


class NotificationRuleUpdateRequest(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=160)
    enabled: bool | None = None
    event_type: NotificationEventType | None = None
    risk_level_threshold: RiskLevel | None = None
    scenario_types: list[str] | None = None
    platforms: list[str] | None = None
    channels: list[NotificationChannel] | None = None
    cron_expr: str | None = Field(default=None, min_length=9, max_length=80)
    cooldown_minutes: int | None = Field(default=None, ge=0)
    channel_config_json: dict[str, Any] | None = None
    last_executed_at: str | None = None


class NotificationDigestRunRequest(BaseModel):
    now: str | None = None


class NotificationInboxUpdateRequest(BaseModel):
    read: bool = True
