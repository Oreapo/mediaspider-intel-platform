from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.task import CollectionTask, TaskRun
from ...domain.repositories.task_repository import CollectionTaskRepository


class JsonCollectionTaskRepository(CollectionTaskRepository):
    def __init__(self, storage_file: Path, runs_file: Path | None = None):
        self.storage_file = storage_file
        self.runs_file = runs_file or storage_file.with_name("task_runs.json")

    def list_tasks(self) -> list[CollectionTask]:
        return sorted(self._load_all(), key=lambda task: task.updated_at, reverse=True)

    def get_task(self, task_id: str) -> CollectionTask | None:
        for task in self._load_all():
            if task.id == task_id:
                return task
        return None

    def save_task(self, task: CollectionTask) -> CollectionTask:
        tasks = self._load_all()
        replaced = False
        for index, existing in enumerate(tasks):
            if existing.id == task.id:
                tasks[index] = task
                replaced = True
                break
        if not replaced:
            tasks.append(task)
        self._save_all(tasks)
        return task

    def delete_task(self, task_id: str) -> bool:
        tasks = self._load_all()
        filtered = [task for task in tasks if task.id != task_id]
        if len(filtered) == len(tasks):
            return False
        self._save_all(filtered)
        return True

    def list_runs(self, task_id: str | None = None) -> list[TaskRun]:
        runs = self._load_runs()
        if task_id is not None:
            runs = [run for run in runs if run.task_id == task_id]
        return sorted(runs, key=lambda run: run.updated_at, reverse=True)

    def get_run(self, run_id: str) -> TaskRun | None:
        for run in self._load_runs():
            if run.id == run_id:
                return run
        return None

    def save_run(self, run: TaskRun) -> TaskRun:
        runs = self._load_runs()
        replaced = False
        for index, existing in enumerate(runs):
            if existing.id == run.id:
                runs[index] = run
                replaced = True
                break
        if not replaced:
            runs.append(run)
        self._save_runs(runs)
        return run

    def _load_all(self) -> list[CollectionTask]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        tasks: list[CollectionTask] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                tasks.append(CollectionTask.model_validate(item))
            except Exception:
                continue
        return tasks

    def _save_all(self, tasks: list[CollectionTask]):
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([task.model_dump(mode="json") for task in tasks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_runs(self) -> list[TaskRun]:
        if not self.runs_file.exists():
            return []
        try:
            raw = json.loads(self.runs_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        runs: list[TaskRun] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                runs.append(TaskRun.model_validate(item))
            except Exception:
                continue
        return runs

    def _save_runs(self, runs: list[TaskRun]):
        self.runs_file.parent.mkdir(parents=True, exist_ok=True)
        self.runs_file.write_text(
            json.dumps([run.model_dump(mode="json") for run in runs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
