from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from .base import TimestampedModel, generate_id
from .platform import PlatformKey


class EntityType(str, Enum):
    CONTENT = "content"
    COMMENT = "comment"
    CREATOR = "creator"
    PRODUCT = "product"
    SELLER = "seller"
    PRICE_SNAPSHOT = "price_snapshot"


class TaskMode(str, Enum):
    SEARCH = "search"
    DETAIL = "detail"
    CREATOR = "creator"
    MONITOR = "monitor"


class ScenarioType(str, Enum):
    LEAD_DIVERSION = "lead_diversion"
    GRAY_RECRUITMENT = "gray_recruitment"
    FRAUD_PROMOTION = "fraud_promotion"
    SELLER_RISK = "seller_risk"
    PRODUCT_RISK = "product_risk"
    TOPIC_WATCH = "topic_watch"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    ENABLED = "enabled"
    DISABLED = "disabled"


class CollectionTask(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("tsk"))
    task_name: str
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
    last_run_at: str | None = None

    @model_validator(mode="after")
    def validate_task_payload(self):
        if self.task_mode == TaskMode.SEARCH and not self.task_payload_json.get("keywords"):
            raise ValueError("search 模式必须提供 keywords")
        if self.task_mode == TaskMode.DETAIL and not self.task_payload_json.get("specified_ids"):
            raise ValueError("detail 模式必须提供 specified_ids")
        if self.task_mode == TaskMode.CREATOR and not self.task_payload_json.get("creator_ids"):
            raise ValueError("creator 模式必须提供 creator_ids")
        if self.task_mode == TaskMode.MONITOR and not self.runtime_payload_json.get("schedule_profile"):
            raise ValueError("monitor 模式必须提供 schedule_profile")
        return self


class TaskRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRun(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("run"))
    task_id: str
    status: TaskRunStatus = TaskRunStatus.PENDING
    trigger_type: str = "manual"
    started_at: str | None = None
    finished_at: str | None = None
    log_path: str = ""
    result_dataset_id: str | None = None
    result_dataset_ids: list[str] = Field(default_factory=list)
    error_message: str = ""
    task_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    run_result_json: dict[str, Any] = Field(default_factory=dict)
