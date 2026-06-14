from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.platform import PlatformKey
from ..models.task import CollectionTask, EntityType, ScenarioType, TaskMode, TaskRun, TaskRunStatus, TaskStatus


class CollectionTaskRepository(ABC):
    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def count_tasks(
        self,
        *,
        platform: PlatformKey | None = None,
        status: TaskStatus | None = None,
        task_mode: TaskMode | None = None,
        entity_type: EntityType | None = None,
        scenario_type: ScenarioType | None = None,
        query: str = "",
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_task(self, task_id: str) -> CollectionTask | None:
        raise NotImplementedError

    @abstractmethod
    def save_task(self, task: CollectionTask) -> CollectionTask:
        raise NotImplementedError

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_runs(
        self,
        task_id: str | None = None,
        *,
        status: TaskRunStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskRun]:
        raise NotImplementedError

    @abstractmethod
    def count_runs(
        self,
        task_id: str | None = None,
        *,
        status: TaskRunStatus | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> TaskRun | None:
        raise NotImplementedError

    @abstractmethod
    def save_run(self, run: TaskRun) -> TaskRun:
        raise NotImplementedError

    @property
    def supports_run_leases(self) -> bool:
        return False

    def acquire_run_lease(
        self,
        task_id: str,
        run_id: str,
        owner_id: str,
        lease_seconds: float,
    ) -> bool:
        return True

    def renew_run_lease(
        self,
        task_id: str,
        run_id: str,
        owner_id: str,
        lease_seconds: float,
    ) -> bool:
        return True

    def release_run_lease(self, task_id: str, run_id: str, owner_id: str) -> bool:
        return True

    def is_run_lease_active(self, task_id: str, run_id: str) -> bool:
        return False

    def count_active_run_leases(self) -> int:
        return 0
