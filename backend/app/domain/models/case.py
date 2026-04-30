from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id


class CaseStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    READY_FOR_EVIDENCE = "ready_for_evidence"
    CLOSED = "closed"


class CasePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseLinkType(str, Enum):
    DATASET = "dataset"
    SIGNAL = "signal"
    ENTITY = "entity"
    ANALYSIS_OUTPUT = "analysis_output"
    EVIDENCE_PACKET = "evidence_packet"


class Case(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("case"))
    case_name: str
    case_type: str
    status: CaseStatus = CaseStatus.OPEN
    priority: CasePriority = CasePriority.MEDIUM
    summary: str = ""
    owner: str = ""


class CaseLink(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("clk"))
    case_id: str
    link_type: CaseLinkType
    target_id: str
    label: str = ""
    source_ref_json: dict[str, Any] = Field(default_factory=dict)


class CaseNote(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("note"))
    case_id: str
    author: str = ""
    body: str
    note_type: str = "investigation"
