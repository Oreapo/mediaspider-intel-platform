from __future__ import annotations

from datetime import datetime
from typing import Any

from ...api.schemas.task import CollectionTaskCreateRequest, CollectionTaskUpdateRequest
from ...domain.models.platform import PlatformKey
from ...domain.models.task import CollectionTask, EntityType, ScenarioType, TaskMode, TaskStatus


class TaskCrudMixin:
    def list_tasks(
        self,
        *,
        platform: PlatformKey | None = None,
        status: TaskStatus | None = None,
        task_mode: TaskMode | None = None,
        entity_type: EntityType | None = None,
        scenario_type: ScenarioType | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[CollectionTask]:
        return self.repository.list_tasks(
            platform=platform,
            status=status,
            task_mode=task_mode,
            entity_type=entity_type,
            scenario_type=scenario_type,
            query=query,
            limit=limit,
            offset=offset,
        )

    def list_tasks_page(
        self,
        *,
        platform: PlatformKey | None = None,
        status: TaskStatus | None = None,
        task_mode: TaskMode | None = None,
        entity_type: EntityType | None = None,
        scenario_type: ScenarioType | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[CollectionTask], int]:
        filters = {
            "platform": platform,
            "status": status,
            "task_mode": task_mode,
            "entity_type": entity_type,
            "scenario_type": scenario_type,
            "query": query,
        }
        return (
            self.repository.list_tasks(**filters, limit=limit, offset=offset),
            self.repository.count_tasks(**filters),
        )

    def get_task(self, task_id: str) -> CollectionTask | None:
        return self.repository.get_task(task_id)

    def create_task(self, payload: CollectionTaskCreateRequest) -> CollectionTask:
        task = CollectionTask(**payload.model_dump())
        return self.repository.save_task(task)

    def update_task(self, task_id: str, payload: CollectionTaskUpdateRequest) -> CollectionTask:
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        updated = existing.model_copy(
            update={
                **payload.model_dump(exclude_unset=True),
                "updated_at": datetime.utcnow(),
            }
        )
        return self.repository.save_task(updated)

    def delete_task(self, task_id: str) -> bool:
        if self.repository.get_task(task_id) is None:
            return False
        active_run = self._active_run(task_id)
        if active_run is not None:
            raise ValueError(
                f"Task {task_id} cannot be deleted while run {active_run.id} is active"
            )
        return self.repository.delete_task(task_id)

    def set_task_status(self, task_id: str, status: TaskStatus) -> CollectionTask:
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        updated = existing.model_copy(update={"status": status, "updated_at": datetime.utcnow()})
        return self.repository.save_task(updated)
