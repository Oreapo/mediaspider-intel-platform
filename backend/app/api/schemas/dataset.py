from __future__ import annotations

from pydantic import BaseModel, Field

from ...domain.models.dataset import DatasetType
from ...domain.models.platform import PlatformKey
from ...domain.models.task import ScenarioType


class DatasetCreateRequest(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=120)
    dataset_type: DatasetType = DatasetType.RAW
    source_platform: PlatformKey
    source_task_id: str | None = None
    source_run_id: str | None = None
    scenario_type: ScenarioType | None = None
    storage_uri: str = ""
    tags: list[str] = Field(default_factory=list)
