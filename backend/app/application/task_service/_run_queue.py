from __future__ import annotations

from datetime import datetime
from queue import Empty
from threading import Event, Thread, current_thread
from time import monotonic

from ...domain.models.task import CollectionTask, TaskRun, TaskRunStatus, TaskStatus
from ._support import TASK_QUEUE_PRIORITY_WEIGHTS


class TaskRunQueueMixin:
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
    ) -> dict[str, object]:
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

    def start_run(
        self,
        task_id: str,
        trigger_type: str = "manual",
        execute_crawler: bool = True,
        retry_attempt: int = 0,
        max_retries: int = 0,
        retry_of_run_id: str | None = None,
        retry_root_run_id: str | None = None,
    ) -> TaskRun:
        run = self._prepare_run(
            task_id,
            trigger_type=trigger_type,
            execute_crawler=execute_crawler,
            retry_attempt=retry_attempt,
            max_retries=max_retries,
            retry_of_run_id=retry_of_run_id,
            retry_root_run_id=retry_root_run_id,
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
        retry_of_run_id: str | None = None,
        retry_root_run_id: str | None = None,
    ) -> TaskRun:
        if not execute_crawler:
            return self.start_run(
                task_id,
                trigger_type=trigger_type,
                execute_crawler=False,
                retry_attempt=retry_attempt,
                max_retries=max_retries,
                retry_of_run_id=retry_of_run_id,
                retry_root_run_id=retry_root_run_id,
            )

        run = self._prepare_run(
            task_id,
            trigger_type=trigger_type,
            execute_crawler=True,
            retry_attempt=retry_attempt,
            max_retries=max_retries,
            retry_of_run_id=retry_of_run_id,
            retry_root_run_id=retry_root_run_id,
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
        retry_of_run_id: str | None,
        retry_root_run_id: str | None,
    ) -> TaskRun:
        queued_at = datetime.utcnow()
        lease_acquired = False
        with self._run_state_lock:
            existing = self.repository.get_task(task_id)
            if existing is None:
                raise ValueError(f"Task {task_id} not found")
            if trigger_type not in {"manual", "manual_retry"} and existing.status == TaskStatus.DISABLED:
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
                    **(
                        {
                            "retry_of_run_id": retry_of_run_id,
                            "retry_root_run_id": retry_root_run_id or retry_of_run_id,
                        }
                        if retry_of_run_id
                        else {}
                    ),
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
