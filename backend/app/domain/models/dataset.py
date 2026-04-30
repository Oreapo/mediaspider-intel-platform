from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import TimestampedModel, generate_id
from .platform import PlatformKey
from .task import EntityType, ScenarioType


class DatasetType(str, Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    ANALYSIS_READY = "analysis_ready"


class Dataset(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("ds"))
    dataset_name: str
    dataset_type: DatasetType
    source_platform: PlatformKey
    source_task_id: str | None = None
    source_run_id: str | None = None
    scenario_type: ScenarioType | None = None
    record_count: int = 0
    storage_uri: str = ""
    schema_version: str = "v1"
    snapshot_time: str | None = None
    tags: list[str] = Field(default_factory=list)


class DatasetItem(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("item"))
    dataset_id: str
    entity_type: EntityType
    source_platform: PlatformKey
    source_entity_id: str
    normalized_json: dict[str, Any] = Field(default_factory=dict)
    raw_ref: str = ""
    published_at: str | None = None
    collected_at: str | None = None
