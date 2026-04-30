from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...domain.models import EntityType, PlatformKey, ScenarioType, TaskMode, TaskStatus


class CollectionTaskCreateRequest(BaseModel):
    task_name: str = Field(min_length=1, max_length=100)
    platform: PlatformKey
    entity_type: EntityType
    task_mode: TaskMode
    scenario_type: ScenarioType
    status: TaskStatus = TaskStatus.ENABLED
    auth_profile_id: str | None = None
    task_payload_json: dict[str, Any] = Field(default_factory=dict)
    filter_payload_json: dict[str, Any] = Field(default_factory=dict)
    runtime_payload_json: dict[str, Any] = Field(default_factory=dict)
    storage_profile_json: dict[str, Any] = Field(default_factory=dict)
    analysis_profile_json: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class CollectionTaskUpdateRequest(BaseModel):
    task_name: str | None = Field(default=None, min_length=1, max_length=100)
    platform: PlatformKey | None = None
    entity_type: EntityType | None = None
    task_mode: TaskMode | None = None
    scenario_type: ScenarioType | None = None
    status: TaskStatus | None = None
    auth_profile_id: str | None = None
    task_payload_json: dict[str, Any] | None = None
    filter_payload_json: dict[str, Any] | None = None
    runtime_payload_json: dict[str, Any] | None = None
    storage_profile_json: dict[str, Any] | None = None
    analysis_profile_json: dict[str, Any] | None = None
    notes: str | None = None


class TaskRunStartRequest(BaseModel):
    trigger_type: str = "manual"
    execute_crawler: bool = True
