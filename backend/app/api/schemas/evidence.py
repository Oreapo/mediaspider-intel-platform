from __future__ import annotations

from pydantic import BaseModel, Field


class EvidencePacketCreateRequest(BaseModel):
    case_id: str = Field(min_length=1)
    packet_name: str = Field(min_length=1, max_length=160)
