from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...domain.models.case import CaseLinkType, CasePriority, CaseStatus


class CaseCreateRequest(BaseModel):
    case_name: str = Field(min_length=1, max_length=160)
    case_type: str = Field(min_length=1, max_length=80)
    status: CaseStatus = CaseStatus.OPEN
    priority: CasePriority = CasePriority.MEDIUM
    summary: str = ""
    owner: str = ""


class CaseUpdateRequest(BaseModel):
    case_name: str | None = Field(default=None, min_length=1, max_length=160)
    case_type: str | None = Field(default=None, min_length=1, max_length=80)
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    summary: str | None = None
    owner: str | None = None


class CaseLinkCreateRequest(BaseModel):
    link_type: CaseLinkType
    target_id: str = Field(min_length=1)
    label: str = ""
    source_ref_json: dict[str, Any] = Field(default_factory=dict)


class CaseNoteCreateRequest(BaseModel):
    author: str = ""
    body: str = Field(min_length=1, max_length=3000)
    note_type: str = Field(default="investigation", min_length=1, max_length=80)
