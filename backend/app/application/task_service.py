from __future__ import annotations

from datetime import datetime
from pathlib import Path
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
    ):
        self.repository = repository
        self.dataset_service = dataset_service
        self.crawler_runner = crawler_runner
        self.auth_profile_resolver = auth_profile_resolver

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

    def list_runs(self, task_id: str | None = None) -> list[TaskRun]:
        return self.repository.list_runs(task_id)

    def get_run(self, run_id: str) -> TaskRun | None:
        return self.repository.get_run(run_id)

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
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        if trigger_type != "manual" and existing.status == TaskStatus.DISABLED:
            raise ValueError(f"Disabled task {task_id} cannot be started by {trigger_type}")
        if trigger_type != "manual":
            active_run = self._active_run(task_id)
            if active_run is not None:
                raise ValueError(f"Task {task_id} already has active run {active_run.id}")
        now = datetime.utcnow()
        updated = existing.model_copy(update={"last_run_at": now.isoformat(), "updated_at": now})
        self.repository.save_task(updated)
        task_for_run = self._apply_auth_profile(updated)
        run = TaskRun(
            task_id=task_id,
            status=TaskRunStatus.RUNNING,
            trigger_type=trigger_type,
            started_at=now.isoformat(),
            task_snapshot_json=task_for_run.model_dump(mode="json"),
            run_result_json={
                "retry_attempt": retry_attempt,
                "max_retries": max_retries,
            },
        )
        run = self.repository.save_run(run)
        if not execute_crawler:
            return run
        return self._execute_crawler_run(task_for_run, run)

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
