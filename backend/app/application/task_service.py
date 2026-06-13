from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, RLock
from time import monotonic
from typing import Callable, Any

from ..domain.models.platform import PlatformKey
from ..domain.models.task import CollectionTask, EntityType, ScenarioType, TaskMode, TaskRun, TaskRunStatus, TaskStatus
from ..domain.repositories.task_repository import CollectionTaskRepository
from ..api.schemas.task import CollectionTaskCreateRequest, CollectionTaskUpdateRequest
from .crawler_runner import CrawlerRunner
from .dataset_service import DatasetService


class CollectionTaskService:
    def __init__(
        self,
        repository: CollectionTaskRepository,
        dataset_service: DatasetService | None = None,
        crawler_runner: CrawlerRunner | None = None,
        auth_profile_resolver: Callable[[str], dict[str, Any]] | None = None,
        max_concurrent_runs: int = 1,
        queue_timeout_seconds: float = 300,
        recover_interrupted_runs: bool = True,
    ):
        self.repository = repository
        self.dataset_service = dataset_service
        self.crawler_runner = crawler_runner
        self.auth_profile_resolver = auth_profile_resolver
        self.max_concurrent_runs = max(1, max_concurrent_runs)
        self.queue_timeout_seconds = max(0.01, queue_timeout_seconds)
        self._run_slots = BoundedSemaphore(self.max_concurrent_runs)
        self._run_state_lock = RLock()
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
            return self._queued_task_runs

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
            if run.status != TaskRunStatus.PENDING:
                raise ValueError(f"Only pending task runs can be cancelled; current status is {run.status.value}")
            cancelled = run.model_copy(
                update={
                    "status": TaskRunStatus.CANCELLED,
                    "finished_at": cancelled_at.isoformat(),
                    "error_message": "Task run cancelled while waiting in queue",
                    "run_result_json": {
                        **run.run_result_json,
                        "cancelled_at": cancelled_at.isoformat(),
                        "cancellation_reason": "user_requested",
                    },
                    "updated_at": cancelled_at,
                }
            )
            return self.repository.save_run(cancelled)

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
        queued_at = datetime.utcnow()
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
                },
            )
            if not execute_crawler:
                updated = existing.model_copy(
                    update={"last_run_at": queued_at.isoformat(), "updated_at": queued_at}
                )
                self.repository.save_task(updated)
                task_for_run = self._apply_auth_profile(updated)
                run = run.model_copy(
                    update={"task_snapshot_json": task_for_run.model_dump(mode="json")}
                )
            run = self.repository.save_run(run)
        if not execute_crawler:
            return run

        acquired = self._run_slots.acquire(blocking=False)
        if not acquired:
            with self._run_state_lock:
                self._queued_task_runs += 1
            try:
                deadline = monotonic() + self.queue_timeout_seconds
                while not acquired:
                    latest_run = self.repository.get_run(run.id)
                    if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                        return latest_run
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        break
                    acquired = self._run_slots.acquire(timeout=min(0.1, remaining))
            finally:
                with self._run_state_lock:
                    self._queued_task_runs = max(0, self._queued_task_runs - 1)
            if not acquired:
                error = f"Task run queue timed out after {self.queue_timeout_seconds:g}s"
                self._fail_run(run, error)
                raise ValueError(error)

        started_at = datetime.utcnow()
        active_registered = False
        try:
            with self._run_state_lock:
                latest_run = self.repository.get_run(run.id)
                if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                    return latest_run
                self._active_task_runs += 1
                active_registered = True
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
                        },
                        "updated_at": started_at,
                    }
                )
                run = self.repository.save_run(run)
            return self._execute_crawler_run(task_for_run, run)
        except Exception as exc:
            latest_run = self.repository.get_run(run.id) or run
            if latest_run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                self._fail_run(latest_run, str(exc))
            raise
        finally:
            if active_registered:
                with self._run_state_lock:
                    self._active_task_runs = max(0, self._active_task_runs - 1)
            self._run_slots.release()

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
                    },
                    "updated_at": datetime.utcnow(),
                }
            )
            with self._run_state_lock:
                return self.repository.save_run(updated)
        except Exception as exc:
            return self._fail_run(run, str(exc))

    def _fail_run(self, run: TaskRun, error_message: str) -> TaskRun:
        updated = run.model_copy(
            update={
                "status": TaskRunStatus.FAILED,
                "finished_at": datetime.utcnow().isoformat(),
                "error_message": error_message,
                "updated_at": datetime.utcnow(),
            }
        )
        with self._run_state_lock:
            return self.repository.save_run(updated)

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
                return run
        return None

    def _max_retries(self, task: CollectionTask) -> int:
        schedule_profile = self._schedule_profile(task)
        raw_value = schedule_profile.get("max_retries", task.runtime_payload_json.get("max_retries", 0))
        try:
            return max(0, int(raw_value))
        except (TypeError, ValueError):
            return 0

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
