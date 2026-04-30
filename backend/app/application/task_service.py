from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..domain.models.task import CollectionTask, TaskRun, TaskRunStatus, TaskStatus
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
    ):
        self.repository = repository
        self.dataset_service = dataset_service
        self.crawler_runner = crawler_runner

    def list_tasks(self) -> list[CollectionTask]:
        return self.repository.list_tasks()

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
    ) -> TaskRun:
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        if trigger_type != "manual" and existing.status == TaskStatus.DISABLED:
            raise ValueError(f"Disabled task {task_id} cannot be started by {trigger_type}")
        now = datetime.utcnow()
        updated = existing.model_copy(update={"last_run_at": now.isoformat(), "updated_at": now})
        self.repository.save_task(updated)
        run = TaskRun(
            task_id=task_id,
            status=TaskRunStatus.RUNNING,
            trigger_type=trigger_type,
            started_at=now.isoformat(),
            task_snapshot_json=existing.model_dump(mode="json"),
        )
        run = self.repository.save_run(run)
        if not execute_crawler:
            return run
        return self._execute_crawler_run(updated, run)

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
