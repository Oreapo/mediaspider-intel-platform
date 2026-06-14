from __future__ import annotations

import os
import socket
from datetime import datetime
from pathlib import Path
from queue import Empty, PriorityQueue
from threading import Condition, Event, RLock, Thread, current_thread
from time import monotonic
from typing import Callable, Any
from uuid import uuid4

from ..domain.models.platform import PlatformKey
from ..domain.models.task import CollectionTask, EntityType, ScenarioType, TaskMode, TaskRun, TaskRunStatus, TaskStatus
from ..domain.repositories.task_repository import CollectionTaskRepository
from ..api.schemas.task import CollectionTaskCreateRequest, CollectionTaskUpdateRequest
from .crawler_runner import CrawlerRunner
from .dataset_service import DatasetService


TASK_QUEUE_PRIORITY_WEIGHTS = {
    "low": 0,
    "normal": 10,
    "high": 20,
    "critical": 30,
}


class CollectionTaskService:
    def __init__(
        self,
        repository: CollectionTaskRepository,
        dataset_service: DatasetService | None = None,
        crawler_runner: CrawlerRunner | None = None,
        auth_profile_resolver: Callable[[str], dict[str, Any]] | None = None,
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
        return self.repository.delete_task(task_id)

    def list_runs(
        self,
        task_id: str | None = None,
        *,
        status: TaskRunStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskRun]:
        return self.repository.list_runs(task_id, status=status, limit=limit, offset=offset)

    def list_runs_page(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        return {
            "runs": self.repository.list_runs(task_id, limit=limit, offset=offset),
            "total": self.repository.count_runs(task_id),
            "status_counts": {
                "succeeded": self.repository.count_runs(task_id, status=TaskRunStatus.SUCCEEDED),
                "failed": self.repository.count_runs(task_id, status=TaskRunStatus.FAILED),
            },
        }

    def get_run(self, run_id: str) -> TaskRun | None:
        return self.repository.get_run(run_id)

    def recover_interrupted_runs(self) -> int:
        recovered = 0
        recovered_at = datetime.utcnow()
        with self._run_state_lock:
            for run in self.repository.list_runs():
                if run.status not in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                    continue
                if (
                    self.repository.supports_run_leases
                    and self.repository.is_run_lease_active(run.task_id, run.id)
                ):
                    continue
                was_pending = run.status == TaskRunStatus.PENDING
                status = TaskRunStatus.CANCELLED if was_pending else TaskRunStatus.FAILED
                reason = (
                    "Queued task run was cancelled during backend restart"
                    if was_pending
                    else "Running task was interrupted by backend restart"
                )
                recovered_run = run.model_copy(
                    update={
                        "status": status,
                        "finished_at": recovered_at.isoformat(),
                        "error_message": reason,
                        "run_result_json": {
                            **run.run_result_json,
                            "recovered_after_restart": True,
                            "previous_status": run.status.value,
                            **(
                                {
                                    "failure_diagnosis": self._failure_diagnosis(
                                        reason,
                                    )
                                }
                                if not was_pending
                                else {}
                            ),
                            "progress": self._progress_payload(
                                "cancelled" if was_pending else "failed",
                                100,
                                recovered_at,
                            ),
                        },
                        "updated_at": recovered_at,
                    }
                )
                self.repository.save_run(recovered_run)
                recovered += 1
        return recovered

    def cancel_run(self, task_id: str, run_id: str) -> TaskRun:
        cancelled_at = datetime.utcnow()
        with self._run_state_lock:
            run = self.repository.get_run(run_id)
            if run is None or run.task_id != task_id:
                raise ValueError("Task run not found")
            if run.status not in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                raise ValueError(
                    f"Only pending or running task runs can be cancelled; current status is {run.status.value}"
                )

            was_running = run.status == TaskRunStatus.RUNNING
            if was_running:
                cancel = getattr(self.crawler_runner, "cancel", None)
                if not callable(cancel):
                    raise ValueError("Running task cancellation is not supported by crawler runner")
                if not cancel(run.id):
                    raise ValueError("Running task process is not available for cancellation")

            cancelled = run.model_copy(
                update={
                    "status": TaskRunStatus.CANCELLED,
                    "finished_at": cancelled_at.isoformat(),
                    "error_message": (
                        "Running task process terminated by user"
                        if was_running
                        else "Task run cancelled while waiting in queue"
                    ),
                    "run_result_json": {
                        **run.run_result_json,
                        "cancelled_at": cancelled_at.isoformat(),
                        "cancellation_reason": "user_requested",
                        "previous_status": run.status.value,
                        "process_termination_requested": was_running,
                        "progress": self._progress_payload(
                            "cancelled",
                            100,
                            cancelled_at,
                        ),
                    },
                    "updated_at": cancelled_at,
                }
            )
            saved = self.repository.save_run(cancelled)
            if not was_running:
                was_submitted = self._submitted_run_priorities.pop(run.id, None) is not None
                if was_submitted and self.repository.supports_run_leases:
                    self.repository.release_run_lease(
                        run.task_id,
                        run.id,
                        self.lease_owner_id,
                    )
            self._queue_condition.notify_all()
            return saved

    def set_task_status(self, task_id: str, status: TaskStatus) -> CollectionTask:
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        updated = existing.model_copy(update={"status": status, "updated_at": datetime.utcnow()})
        return self.repository.save_task(updated)

    def start_run(
        self,
        task_id: str,
        trigger_type: str = "manual",
        execute_crawler: bool = True,
        retry_attempt: int = 0,
        max_retries: int = 0,
    ) -> TaskRun:
        run = self._prepare_run(
            task_id,
            trigger_type=trigger_type,
            execute_crawler=execute_crawler,
            retry_attempt=retry_attempt,
            max_retries=max_retries,
        )
        if not execute_crawler:
            return run
        return self.execute_run(run.id)

    def submit_run(
        self,
        task_id: str,
        trigger_type: str = "manual",
        execute_crawler: bool = True,
        retry_attempt: int = 0,
        max_retries: int = 0,
    ) -> TaskRun:
        if not execute_crawler:
            return self.start_run(
                task_id,
                trigger_type=trigger_type,
                execute_crawler=False,
                retry_attempt=retry_attempt,
                max_retries=max_retries,
            )

        run = self._prepare_run(
            task_id,
            trigger_type=trigger_type,
            execute_crawler=True,
            retry_attempt=retry_attempt,
            max_retries=max_retries,
        )
        submitted_at = datetime.utcnow()
        run = run.model_copy(
            update={
                "run_result_json": {
                    **run.run_result_json,
                    "execution_mode": "background_worker",
                    "submitted_at": submitted_at.isoformat(),
                    "progress": self._progress_payload(
                        "submitted",
                        5,
                        submitted_at,
                    ),
                },
                "updated_at": submitted_at,
            }
        )
        with self._run_state_lock:
            run = self.repository.save_run(run)
        priority = str(run.run_result_json.get("queue_priority", "normal"))
        priority_weight = int(run.run_result_json.get("queue_priority_weight", 10))
        with self._queue_condition:
            self._queue_sequence += 1
            self._submitted_run_priorities[run.id] = priority
            self._background_queue.put((-priority_weight, self._queue_sequence, run.id))
            self._ensure_background_workers_locked()
            self._ensure_background_lease_monitor_locked()
            self._queue_condition.notify_all()
        return run

    def execute_run(self, run_id: str) -> TaskRun:
        run = self.repository.get_run(run_id)
        if run is None:
            raise ValueError(f"Task run {run_id} not found")
        if run.status != TaskRunStatus.PENDING:
            if self.repository.supports_run_leases:
                self.repository.release_run_lease(
                    run.task_id,
                    run.id,
                    self.lease_owner_id,
                )
            return run

        existing = self.repository.get_task(run.task_id)
        if existing is None:
            failed = self._fail_run(run, f"Task {run.task_id} not found before execution")
            if self.repository.supports_run_leases:
                self.repository.release_run_lease(
                    run.task_id,
                    run.id,
                    self.lease_owner_id,
                )
            return failed

        try:
            task_for_run = CollectionTask.model_validate(run.task_snapshot_json)
            queued_at = datetime.fromisoformat(
                str(run.run_result_json.get("queued_at") or run.created_at.isoformat())
            )
        except (TypeError, ValueError) as exc:
            failed = self._fail_run(run, f"Task run payload is invalid: {exc}")
            if self.repository.supports_run_leases:
                self.repository.release_run_lease(
                    run.task_id,
                    run.id,
                    self.lease_owner_id,
                )
            return failed

        priority = str(run.run_result_json.get("queue_priority", "normal"))
        priority_weight = int(
            run.run_result_json.get(
                "queue_priority_weight",
                TASK_QUEUE_PRIORITY_WEIGHTS.get(priority, 10),
            )
        )
        if self.repository.supports_run_leases and not self.repository.renew_run_lease(
            run.task_id,
            run.id,
            self.lease_owner_id,
            self.lease_seconds,
        ):
            return self._fail_run(run, "Task run lease lost before execution")

        lease_stop, lease_lost, lease_thread = self._start_lease_heartbeat(run.task_id, run.id)
        try:
            return self._run_with_capacity(
                existing=existing,
                task_for_run=task_for_run,
                run=run,
                queued_at=queued_at,
                queue_priority=priority,
                queue_priority_weight=priority_weight,
                lease_lost=lease_lost,
            )
        finally:
            lease_stop.set()
            if lease_thread is not None:
                lease_thread.join(timeout=1)
            if self.repository.supports_run_leases:
                self.repository.release_run_lease(
                    run.task_id,
                    run.id,
                    self.lease_owner_id,
                )

    def _prepare_run(
        self,
        task_id: str,
        *,
        trigger_type: str,
        execute_crawler: bool,
        retry_attempt: int,
        max_retries: int,
    ) -> TaskRun:
        queued_at = datetime.utcnow()
        lease_acquired = False
        with self._run_state_lock:
            existing = self.repository.get_task(task_id)
            if existing is None:
                raise ValueError(f"Task {task_id} not found")
            if trigger_type != "manual" and existing.status == TaskStatus.DISABLED:
                raise ValueError(f"Disabled task {task_id} cannot be started by {trigger_type}")
            active_run = self._active_run(task_id)
            if active_run is not None:
                raise ValueError(f"Task {task_id} already has active run {active_run.id}")
            task_for_run = self._apply_auth_profile(existing)
            queue_priority, queue_priority_weight = self._queue_priority(task_for_run)
            run = TaskRun(
                task_id=task_id,
                status=TaskRunStatus.PENDING if execute_crawler else TaskRunStatus.RUNNING,
                trigger_type=trigger_type,
                started_at=None if execute_crawler else queued_at.isoformat(),
                task_snapshot_json=task_for_run.model_dump(mode="json"),
                run_result_json={
                    "retry_attempt": retry_attempt,
                    "max_retries": max_retries,
                    "queued_at": queued_at.isoformat(),
                    "queue_priority": queue_priority,
                    "queue_priority_weight": queue_priority_weight,
                    "lease_supported": self.repository.supports_run_leases,
                    "lease_owner_id": (
                        self.lease_owner_id if self.repository.supports_run_leases else ""
                    ),
                    "lease_seconds": (
                        self.lease_seconds if self.repository.supports_run_leases else 0
                    ),
                    "progress": self._progress_payload(
                        "queued" if execute_crawler else "started",
                        0 if execute_crawler else 10,
                        queued_at,
                    ),
                },
            )
            if execute_crawler:
                lease_acquired = self.repository.acquire_run_lease(
                    task_id,
                    run.id,
                    self.lease_owner_id,
                    self.lease_seconds,
                )
                if not lease_acquired:
                    raise ValueError(f"Task {task_id} already has active run lease")
            if not execute_crawler:
                updated = existing.model_copy(
                    update={"last_run_at": queued_at.isoformat(), "updated_at": queued_at}
                )
                self.repository.save_task(updated)
                task_for_run = self._apply_auth_profile(updated)
                run = run.model_copy(
                    update={"task_snapshot_json": task_for_run.model_dump(mode="json")}
                )
            try:
                run = self.repository.save_run(run)
            except Exception:
                if lease_acquired:
                    self.repository.release_run_lease(
                        task_id,
                        run.id,
                        self.lease_owner_id,
                    )
                raise
        return run

    def _ensure_background_workers_locked(self) -> None:
        self._background_workers = {
            worker for worker in self._background_workers if worker.is_alive()
        }
        desired_workers = min(
            self.max_concurrent_runs,
            len(self._submitted_run_priorities),
        )
        while len(self._background_workers) < desired_workers:
            worker = Thread(
                target=self._background_worker,
                name=f"task-worker-{self.lease_owner_id}-{len(self._background_workers) + 1}",
                daemon=True,
            )
            self._background_workers.add(worker)
            worker.start()

    def _background_worker(self) -> None:
        worker = current_thread()
        try:
            while True:
                try:
                    _, _, run_id = self._background_queue.get(timeout=1)
                except Empty:
                    return
                try:
                    with self._queue_condition:
                        self._submitted_run_priorities.pop(run_id, None)
                        self._queue_condition.notify_all()
                    self.execute_run(run_id)
                except Exception as exc:
                    run = self.repository.get_run(run_id)
                    if run is not None and run.status in {
                        TaskRunStatus.PENDING,
                        TaskRunStatus.RUNNING,
                    }:
                        self._fail_run(run, f"Background task execution failed: {exc}")
                finally:
                    self._background_queue.task_done()
        finally:
            with self._queue_condition:
                self._background_workers.discard(worker)
                if self._submitted_run_priorities:
                    self._ensure_background_workers_locked()

    def _ensure_background_lease_monitor_locked(self) -> None:
        if not self.repository.supports_run_leases:
            return
        if self._background_lease_monitor is not None and self._background_lease_monitor.is_alive():
            return
        monitor = Thread(
            target=self._monitor_submitted_run_leases,
            name=f"task-submission-leases-{self.lease_owner_id}",
            daemon=True,
        )
        self._background_lease_monitor = monitor
        monitor.start()

    def _monitor_submitted_run_leases(self) -> None:
        interval = max(1.0, self.lease_seconds / 3)
        while True:
            with self._queue_condition:
                if not self._submitted_run_priorities:
                    self._background_lease_monitor = None
                    return
                self._queue_condition.wait(timeout=interval)
                run_ids = list(self._submitted_run_priorities)
            for run_id in run_ids:
                run = self.repository.get_run(run_id)
                if run is None or run.status != TaskRunStatus.PENDING:
                    with self._queue_condition:
                        self._submitted_run_priorities.pop(run_id, None)
                    continue
                if self.repository.renew_run_lease(
                    run.task_id,
                    run.id,
                    self.lease_owner_id,
                    self.lease_seconds,
                ):
                    continue
                self._fail_run(run, "Task run lease lost while waiting for background worker")
                with self._queue_condition:
                    self._submitted_run_priorities.pop(run_id, None)

    def _run_with_capacity(
        self,
        *,
        existing: CollectionTask,
        task_for_run: CollectionTask,
        run: TaskRun,
        queued_at: datetime,
        queue_priority: str,
        queue_priority_weight: int,
        lease_lost: Event,
    ) -> TaskRun:
        task_id = run.task_id
        active_registered = False
        queue_timed_out = False
        cancelled_run: TaskRun | None = None
        lease_error = ""
        with self._queue_condition:
            if self._active_task_runs < self.max_concurrent_runs and not self._queued_run_priorities:
                self._active_task_runs += 1
                active_registered = True
            else:
                run = self._save_run_progress(
                    run,
                    "waiting_for_capacity",
                    10,
                )
                self._queue_sequence += 1
                self._queued_run_priorities[run.id] = (
                    queue_priority_weight,
                    self._queue_sequence,
                    queue_priority,
                )
                self._queued_task_runs = len(self._queued_run_priorities)
                deadline = monotonic() + self.queue_timeout_seconds
                try:
                    while not active_registered:
                        if lease_lost.is_set():
                            lease_error = "Task run lease lost while waiting in queue"
                            break
                        latest_run = self.repository.get_run(run.id)
                        if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                            cancelled_run = latest_run
                            break

                        next_run_id = self._next_queued_run_id()
                        if (
                            next_run_id == run.id
                            and self._active_task_runs < self.max_concurrent_runs
                        ):
                            self._queued_run_priorities.pop(run.id, None)
                            self._queued_task_runs = len(self._queued_run_priorities)
                            self._active_task_runs += 1
                            active_registered = True
                            break

                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            queue_timed_out = True
                            break
                        self._queue_condition.wait(timeout=min(0.1, remaining))
                finally:
                    if run.id in self._queued_run_priorities:
                        self._queued_run_priorities.pop(run.id, None)
                        self._queued_task_runs = len(self._queued_run_priorities)
                        self._queue_condition.notify_all()

        if cancelled_run is not None:
            return cancelled_run
        if lease_error:
            self._fail_run(run, lease_error)
            raise ValueError(lease_error)
        if queue_timed_out:
            error = f"Task run queue timed out after {self.queue_timeout_seconds:g}s"
            self._fail_run(run, error)
            raise ValueError(error)

        started_at = datetime.utcnow()
        try:
            with self._run_state_lock:
                latest_run = self.repository.get_run(run.id)
                if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                    return latest_run
                latest_task = self.repository.get_task(task_id) or existing
                updated = latest_task.model_copy(
                    update={"last_run_at": started_at.isoformat(), "updated_at": started_at}
                )
                self.repository.save_task(updated)
                task_for_run = self._apply_auth_profile(updated)
                queue_wait_seconds = max(0.0, (started_at - queued_at).total_seconds())
                run = run.model_copy(
                    update={
                        "status": TaskRunStatus.RUNNING,
                        "started_at": started_at.isoformat(),
                        "task_snapshot_json": task_for_run.model_dump(mode="json"),
                        "run_result_json": {
                            **run.run_result_json,
                            "queue_wait_seconds": round(queue_wait_seconds, 3),
                            "max_concurrent_runs": self.max_concurrent_runs,
                            "progress": self._progress_payload(
                                "collecting",
                                25,
                                started_at,
                            ),
                        },
                        "updated_at": started_at,
                    }
                )
                run = self.repository.save_run(run)
            result = self._execute_crawler_run(task_for_run, run)
            if lease_lost.is_set() and result.status != TaskRunStatus.CANCELLED:
                return self._fail_run(result, "Task run lease lost during execution")
            return result
        except Exception as exc:
            latest_run = self.repository.get_run(run.id) or run
            if latest_run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                self._fail_run(latest_run, str(exc))
            raise
        finally:
            if active_registered:
                with self._queue_condition:
                    self._active_task_runs = max(0, self._active_task_runs - 1)
                    self._queue_condition.notify_all()

    def _start_lease_heartbeat(
        self,
        task_id: str,
        run_id: str,
    ) -> tuple[Event, Event, Thread | None]:
        stop = Event()
        lost = Event()
        if not self.repository.supports_run_leases:
            return stop, lost, None

        interval = max(1.0, self.lease_seconds / 3)

        def renew() -> None:
            while not stop.wait(interval):
                if self.repository.renew_run_lease(
                    task_id,
                    run_id,
                    self.lease_owner_id,
                    self.lease_seconds,
                ):
                    continue
                lost.set()
                with self._queue_condition:
                    self._queue_condition.notify_all()
                cancel = getattr(self.crawler_runner, "cancel", None)
                if callable(cancel):
                    cancel(run_id)
                return

        thread = Thread(
            target=renew,
            name=f"task-lease-{run_id}",
            daemon=True,
        )
        thread.start()
        return stop, lost, thread

    def _next_queued_run_id(self) -> str | None:
        if not self._queued_run_priorities:
            return None
        return max(
            self._queued_run_priorities,
            key=lambda run_id: (
                self._queued_run_priorities[run_id][0],
                -self._queued_run_priorities[run_id][1],
            ),
        )

    def _queue_priority(self, task: CollectionTask) -> tuple[str, int]:
        raw_priority = str(task.runtime_payload_json.get("queue_priority", "normal")).lower()
        priority = "normal" if raw_priority == "medium" else raw_priority
        if priority not in TASK_QUEUE_PRIORITY_WEIGHTS:
            priority = "normal"
        return priority, TASK_QUEUE_PRIORITY_WEIGHTS[priority]

    def run_scheduled_tasks(
        self,
        *,
        now: datetime | None = None,
        execute_crawler: bool = True,
    ) -> dict[str, object]:
        current = now or datetime.utcnow()
        results: list[dict[str, object]] = []
        for task in self.repository.list_tasks():
            if task.status != TaskStatus.ENABLED:
                continue
            schedule_profile = self._schedule_profile(task)
            if not schedule_profile:
                continue
            cron_expr = str(schedule_profile.get("cron") or "").strip()
            if not cron_expr or not self._cron_matches(cron_expr, current):
                continue
            if not self._schedule_window_elapsed(task, current):
                continue
            active_run = self._active_run(task.id)
            if active_run is not None:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "skipped",
                        "reason": "active_run_exists",
                        "active_run_id": active_run.id,
                    }
                )
                continue
            max_retries = self._max_retries(task)
            retry_attempt = self._next_retry_attempt(task.id, max_retries)
            if retry_attempt > max_retries:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "skipped",
                        "reason": "retry_exhausted",
                        "retry_attempt": retry_attempt - 1,
                        "max_retries": max_retries,
                    }
                )
                continue
            if not execute_crawler:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "ready",
                        "reason": "preflight",
                        "retry_attempt": retry_attempt,
                        "max_retries": max_retries,
                    }
                )
                continue
            try:
                run = self.start_run(
                    task.id,
                    trigger_type="cron",
                    execute_crawler=execute_crawler,
                    retry_attempt=retry_attempt,
                    max_retries=max_retries,
                )
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "started" if not execute_crawler else run.status.value,
                        "retry_attempt": retry_attempt,
                        "max_retries": max_retries,
                        "run": run.model_dump(mode="json"),
                    }
                )
            except ValueError as exc:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "failed",
                        "error": str(exc),
                    }
                )
        return {"ran_at": current.isoformat(), "results": results}

    def diagnose_crawler(self, task_id: str) -> dict[str, object]:
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        if self.crawler_runner is None:
            return {
                "ready": False,
                "errors": ["Crawler runner is not configured"],
                "warnings": [],
                "command": [],
            }
        diagnose = getattr(self.crawler_runner, "diagnose", None)
        if not callable(diagnose):
            return {
                "ready": False,
                "errors": ["Crawler runner does not support diagnostics"],
                "warnings": [],
                "command": [],
            }
        return diagnose(self._apply_auth_profile(existing))

    def _execute_crawler_run(self, task: CollectionTask, run: TaskRun) -> TaskRun:
        if self.crawler_runner is None:
            return self._fail_run(run, "Crawler runner is not configured")
        if self.dataset_service is None:
            return self._fail_run(run, "Dataset service is not configured")

        try:
            result = self.crawler_runner.run(task, run)
            with self._run_state_lock:
                latest_run = self.repository.get_run(run.id)
                if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                    return latest_run
                run = self._save_run_progress(
                    latest_run or run,
                    "importing_results",
                    80,
                )

            dataset_ids: list[str] = []
            for output_file in result.output_files:
                dataset = self.dataset_service.create_dataset_from_file(
                    source_file=output_file,
                    dataset_name=self._dataset_name(task, output_file),
                    source_platform=task.platform,
                    source_task_id=task.id,
                    source_run_id=run.id,
                    scenario_type=task.scenario_type,
                    destination_prefix=f"crawler_runs/{run.id}",
                    tags=["crawler", self._item_type(output_file), task.task_mode.value],
                )
                dataset_ids.append(dataset.id)

            finished_at = (result.finished_at or datetime.utcnow()).isoformat()
            status = TaskRunStatus.SUCCEEDED if result.return_code == 0 else TaskRunStatus.FAILED
            finished_progress_at = datetime.utcnow()
            updated = run.model_copy(
                update={
                    "status": status,
                    "finished_at": finished_at,
                    "log_path": str(result.log_path),
                    "result_dataset_id": dataset_ids[0] if dataset_ids else None,
                    "result_dataset_ids": dataset_ids,
                    "error_message": result.error_message,
                    "run_result_json": {
                        **run.run_result_json,
                        "return_code": result.return_code,
                        "command": result.redacted_command,
                        "output_files": [str(path) for path in result.output_files],
                        "dataset_ids": dataset_ids,
                        **(
                            {
                                "failure_diagnosis": self._failure_diagnosis(
                                    result.error_message,
                                    return_code=result.return_code,
                                )
                            }
                            if status == TaskRunStatus.FAILED
                            else {}
                        ),
                        "progress": self._progress_payload(
                            "completed" if status == TaskRunStatus.SUCCEEDED else "failed",
                            100,
                            finished_progress_at,
                        ),
                    },
                    "updated_at": finished_progress_at,
                }
            )
            with self._run_state_lock:
                latest_run = self.repository.get_run(run.id)
                if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                    return latest_run
                return self.repository.save_run(updated)
        except Exception as exc:
            return self._fail_run(run, str(exc))

    def _fail_run(self, run: TaskRun, error_message: str) -> TaskRun:
        failed_at = datetime.utcnow()
        updated = run.model_copy(
            update={
                "status": TaskRunStatus.FAILED,
                "finished_at": failed_at.isoformat(),
                "error_message": error_message,
                "run_result_json": {
                    **run.run_result_json,
                    "failure_diagnosis": self._failure_diagnosis(error_message),
                    "progress": self._progress_payload("failed", 100, failed_at),
                },
                "updated_at": failed_at,
            }
        )
        with self._run_state_lock:
            latest_run = self.repository.get_run(run.id)
            if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                return latest_run
            return self.repository.save_run(updated)

    def _save_run_progress(
        self,
        run: TaskRun,
        stage: str,
        percent: int,
    ) -> TaskRun:
        updated_at = datetime.utcnow()
        updated = run.model_copy(
            update={
                "run_result_json": {
                    **run.run_result_json,
                    "progress": self._progress_payload(stage, percent, updated_at),
                },
                "updated_at": updated_at,
            }
        )
        return self.repository.save_run(updated)

    def _progress_payload(
        self,
        stage: str,
        percent: int,
        updated_at: datetime,
    ) -> dict[str, object]:
        return {
            "stage": stage,
            "percent": max(0, min(100, int(percent))),
            "updated_at": updated_at.isoformat(),
        }

    def _dataset_name(self, task: CollectionTask, output_file: Path) -> str:
        return f"{task.task_name} / {self._item_type(output_file)} / {output_file.stem}"

    def _item_type(self, output_file: Path) -> str:
        parts = output_file.stem.split("_")
        if len(parts) >= 2:
            return parts[-2]
        return "records"

    def _apply_auth_profile(self, task: CollectionTask) -> CollectionTask:
        if not task.auth_profile_id or self.auth_profile_resolver is None:
            return task
        auth_payload = self.auth_profile_resolver(task.auth_profile_id)
        runtime_payload = {**task.runtime_payload_json, **auth_payload}
        return task.model_copy(update={"runtime_payload_json": runtime_payload})

    def _schedule_profile(self, task: CollectionTask) -> dict[str, object]:
        profile = task.runtime_payload_json.get("schedule_profile")
        return profile if isinstance(profile, dict) else {}

    def _active_run(self, task_id: str) -> TaskRun | None:
        for run in self.repository.list_runs(task_id):
            if run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                if (
                    self.repository.supports_run_leases
                    and not self.repository.is_run_lease_active(task_id, run.id)
                ):
                    recovered_at = datetime.utcnow()
                    was_pending = run.status == TaskRunStatus.PENDING
                    self.repository.save_run(
                        run.model_copy(
                            update={
                                "status": (
                                    TaskRunStatus.CANCELLED
                                    if was_pending
                                    else TaskRunStatus.FAILED
                                ),
                                "finished_at": recovered_at.isoformat(),
                                "error_message": (
                                    "Queued task run lease expired"
                                    if was_pending
                                    else "Running task lease expired"
                                ),
                                "run_result_json": {
                                    **run.run_result_json,
                                    "recovered_after_lease_expiry": True,
                                    "previous_status": run.status.value,
                                    **(
                                        {
                                            "failure_diagnosis": self._failure_diagnosis(
                                                "Running task lease expired",
                                            )
                                        }
                                        if not was_pending
                                        else {}
                                    ),
                                    "progress": self._progress_payload(
                                        "cancelled" if was_pending else "failed",
                                        100,
                                        recovered_at,
                                    ),
                                },
                                "updated_at": recovered_at,
                            }
                        )
                    )
                    continue
                return run
        return None

    def _max_retries(self, task: CollectionTask) -> int:
        schedule_profile = self._schedule_profile(task)
        raw_value = schedule_profile.get("max_retries", task.runtime_payload_json.get("max_retries", 0))
        try:
            return max(0, int(raw_value))
        except (TypeError, ValueError):
            return 0

    def _failure_diagnosis(
        self,
        error_message: str,
        *,
        return_code: int | None = None,
    ) -> dict[str, object]:
        normalized = error_message.strip().lower()

        if return_code == 124 or "timed out" in normalized or "timeout" in normalized:
            code = "timeout"
            retryable = True
            suggestions = ["increase_timeout", "reduce_scope", "check_network"]
        elif any(
            marker in normalized
            for marker in (
                "cookie",
                "login",
                "auth",
                "credential",
                "unauthorized",
                "forbidden",
                "扫码",
                "登录",
            )
        ):
            code = "authentication"
            retryable = False
            suggestions = ["refresh_auth_profile", "diagnose_crawler"]
        elif any(
            marker in normalized
            for marker in (
                "root not found",
                "entrypoint",
                "not configured",
                "does not support",
                "requires task_payload_json",
                "requires runtime_payload_json",
                "save_option must",
                "has no mediacrawler",
            )
        ):
            code = "configuration"
            retryable = False
            suggestions = ["diagnose_crawler", "check_crawler_config"]
        elif any(
            marker in normalized
            for marker in (
                "connection",
                "network",
                "dns",
                "proxy",
                "ssl",
                "http 429",
                "too many requests",
                "连接",
                "网络",
                "代理",
            )
        ):
            code = "network"
            retryable = True
            suggestions = ["check_network", "check_proxy", "retry_run"]
        elif any(
            marker in normalized
            for marker in (
                "permission denied",
                "no space left",
                "read-only",
                "storage",
                "dataset",
                "json decode",
                "csv",
                "入库",
                "存储",
            )
        ):
            code = "storage"
            retryable = False
            suggestions = ["check_storage", "inspect_log"]
        elif "backend restart" in normalized or "lease expired" in normalized:
            code = "interrupted"
            retryable = True
            suggestions = ["retry_run", "check_backend_stability"]
        elif return_code is not None:
            code = "crawler_exit"
            retryable = True
            suggestions = ["inspect_log", "diagnose_crawler", "retry_run"]
        else:
            code = "unexpected_error"
            retryable = False
            suggestions = ["inspect_log", "diagnose_crawler"]

        return {
            "code": code,
            "retryable": retryable,
            "suggestions": suggestions,
            "return_code": return_code,
        }

    def _next_retry_attempt(self, task_id: str, max_retries: int) -> int:
        failed_attempts = 0
        for run in self.repository.list_runs(task_id):
            if run.trigger_type != "cron":
                continue
            if run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                return max_retries + 1
            if run.status == TaskRunStatus.SUCCEEDED:
                return 0
            if run.status == TaskRunStatus.FAILED:
                failed_attempts += 1
                continue
            return 0
        return failed_attempts

    def _schedule_window_elapsed(self, task: CollectionTask, now: datetime) -> bool:
        if not task.last_run_at:
            return True
        try:
            last_run_at = datetime.fromisoformat(task.last_run_at)
        except ValueError:
            return True
        return last_run_at.replace(second=0, microsecond=0) < now.replace(second=0, microsecond=0)

    def _parse_cron(self, cron_expr: str) -> list[str]:
        fields = cron_expr.split()
        if len(fields) != 5:
            raise ValueError("cron_expr must contain five fields")
        return fields

    def _cron_matches(self, cron_expr: str, now: datetime) -> bool:
        try:
            minute, hour, day, month, weekday = self._parse_cron(cron_expr)
            return (
                self._field_matches(minute, now.minute, 0, 59)
                and self._field_matches(hour, now.hour, 0, 23)
                and self._field_matches(day, now.day, 1, 31)
                and self._field_matches(month, now.month, 1, 12)
                and self._field_matches(weekday, now.weekday(), 0, 6)
            )
        except ValueError:
            return False

    def _field_matches(self, field: str, value: int, minimum: int, maximum: int) -> bool:
        for part in field.split(","):
            if part == "*":
                return True
            if part.startswith("*/"):
                step = int(part[2:])
                if step <= 0:
                    raise ValueError("cron step must be positive")
                if value % step == 0:
                    return True
                continue
            if "-" in part:
                start, end = [int(item) for item in part.split("-", 1)]
                if start <= value <= end:
                    return True
                continue
            number = int(part)
            if number < minimum or number > maximum:
                raise ValueError("cron field value out of range")
            if value == number:
                return True
        return False
