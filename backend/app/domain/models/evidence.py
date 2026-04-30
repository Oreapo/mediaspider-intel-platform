from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id


class EvidencePacket(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("evp"))
    case_id: str
    packet_name: str
    storage_uri: str
    manifest_json: dict[str, Any] = Field(default_factory=dict)
