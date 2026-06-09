from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id


class AuditEvent(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("aud"))
    action: str
    actor_username: str
    actor_role: str
    target_type: str
    target_id: str
    summary: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
