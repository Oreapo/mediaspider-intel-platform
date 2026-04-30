from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.task import CollectionTask, TaskRun


class CollectionTaskRepository(ABC):
    @abstractmethod
    def list_tasks(self) -> list[CollectionTask]:
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
    def list_runs(self, task_id: str | None = None) -> list[TaskRun]:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> TaskRun | None:
        raise NotImplementedError

    @abstractmethod
    def save_run(self, run: TaskRun) -> TaskRun:
        raise NotImplementedError
