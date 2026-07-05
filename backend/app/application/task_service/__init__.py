from __future__ import annotations

import os
import socket
from queue import PriorityQueue
from threading import Condition, RLock, Thread
from typing import Callable, Any
from uuid import uuid4

from ...domain.repositories.task_repository import CollectionTaskRepository
from ..crawler_runner import CrawlerRunner
from ..dataset_service import DatasetService
from ._crud import TaskCrudMixin
from ._execution import TaskExecutionMixin
from ._retry import TaskRetryMixin
from ._run_queue import TaskRunQueueMixin
from ._scheduler import TaskSchedulerMixin
from ._support import TASK_QUEUE_PRIORITY_WEIGHTS, TaskRunSupportMixin


__all__ = ["CollectionTaskService", "TASK_QUEUE_PRIORITY_WEIGHTS"]


class CollectionTaskService(
    TaskCrudMixin,
    TaskSchedulerMixin,
    TaskRetryMixin,
    TaskExecutionMixin,
    TaskRunQueueMixin,
    TaskRunSupportMixin,
):
    def __init__(
        self,
        repository: CollectionTaskRepository,
        dataset_service: DatasetService | None = None,
        crawler_runner: CrawlerRunner | None = None,
        auth_profile_resolver: Callable[[str], dict[str, Any]] | None = None,
        analysis_job_creator: Callable[..., Any] | None = None,
        signal_extractor: Callable[..., list[Any]] | None = None,
        max_concurrent_runs: int = 1,
        queue_timeout_seconds: float = 300,
        lease_seconds: float = 30,
        lease_owner_id: str | None = None,
        recover_interrupted_runs: bool = True,
    ):
        self.repository = repository
        self.dataset_service = dataset_service
        self.crawler_runner = crawler_runner
        self.auth_profile_resolver = auth_profile_resolver
        self.analysis_job_creator = analysis_job_creator
        self.signal_extractor = signal_extractor
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self.queue_timeout_seconds = max(0.01, queue_timeout_seconds)
        self.lease_seconds = max(3.0, lease_seconds)
        self.lease_owner_id = lease_owner_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        )
        self._run_state_lock = RLock()
        self._queue_condition = Condition(self._run_state_lock)
        self._queued_run_priorities: dict[str, tuple[int, int, str]] = {}
        self._submitted_run_priorities: dict[str, str] = {}
        self._background_queue: PriorityQueue[tuple[int, int, str]] = PriorityQueue()
        self._background_workers: set[Thread] = set()
        self._background_lease_monitor: Thread | None = None
        self._queue_sequence = 0
        self._active_task_runs = 0
        self._queued_task_runs = 0
        self.recovered_task_runs = self.recover_interrupted_runs() if recover_interrupted_runs else 0

    @property
    def active_task_runs(self) -> int:
        with self._run_state_lock:
            return self._active_task_runs

    def set_analysis_job_creator(self, creator: Callable[..., Any]) -> None:
        self.analysis_job_creator = creator

    def set_signal_extractor(self, extractor: Callable[..., list[Any]]) -> None:
        self.signal_extractor = extractor

    @property
    def queued_task_runs(self) -> int:
        with self._run_state_lock:
            return self._queued_task_runs + len(self._submitted_run_priorities)

    @property
    def queued_task_priority_counts(self) -> dict[str, int]:
        with self._run_state_lock:
            counts = {priority: 0 for priority in TASK_QUEUE_PRIORITY_WEIGHTS}
            for _, _, priority in self._queued_run_priorities.values():
                counts[priority] += 1
            for priority in self._submitted_run_priorities.values():
                counts[priority] += 1
            return counts

    @property
    def background_worker_count(self) -> int:
        with self._run_state_lock:
            self._background_workers = {
                worker for worker in self._background_workers if worker.is_alive()
            }
            return len(self._background_workers)

    @property
    def run_leases_supported(self) -> bool:
        return self.repository.supports_run_leases

    @property
    def active_run_leases(self) -> int:
        return self.repository.count_active_run_leases()
