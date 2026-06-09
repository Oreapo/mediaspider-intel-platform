from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ...domain.models.platform import AuthType, PlatformKey


class PlatformFieldOption(BaseModel):
    value: str
    label: str


class PlatformFieldSchema(BaseModel):
    key: str
    label: str
    group: Literal["base", "input", "filters", "runtime", "storage", "analysis", "auth"]
    control: Literal["text", "textarea", "number", "select", "switch", "tags"]
    required: bool = False
    placeholder: str = ""
    help_text: str = ""
    default: Any = None
    visible_for_modes: list[str] = Field(default_factory=list)
    options: list[PlatformFieldOption] = Field(default_factory=list)


class PlatformTaskModelResponse(BaseModel):
    platform: str
    label: str
    summary: str
    supported_entity_types: list[str]
    supported_modes: list[str]
    supported_signal_extractors: list[str] = Field(default_factory=list)
    supported_analysis_types: list[str] = Field(default_factory=list)
    task_fields: list[PlatformFieldSchema]


class PlatformProfileCreateRequest(BaseModel):
    platform: PlatformKey
    profile_name: str = Field(min_length=1, max_length=100)
    auth_type: AuthType
    credentials_ref: str = ""
    settings_json: dict[str, Any] = Field(default_factory=dict)


class PlatformProfileUpdateRequest(BaseModel):
    platform: PlatformKey | None = None
    profile_name: str | None = Field(default=None, min_length=1, max_length=100)
    auth_type: AuthType | None = None
    credentials_ref: str | None = None
    settings_json: dict[str, Any] | None = None
