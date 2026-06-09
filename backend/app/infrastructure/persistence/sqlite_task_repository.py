from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.task import CollectionTask, TaskRun
from ...domain.repositories.task_repository import CollectionTaskRepository


class SQLiteCollectionTaskRepository(CollectionTaskRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_tasks(self) -> list[CollectionTask]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM collection_tasks ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: str) -> CollectionTask | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collection_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return self._row_to_task(row) if row is not None else None

    def save_task(self, task: CollectionTask) -> CollectionTask:
        payload = task.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_tasks (
                    id,
                    task_name,
                    platform,
                    entity_type,
                    task_mode,
                    scenario_type,
                    status,
                    auth_profile_id,
                    task_payload_json,
                    filter_payload_json,
                    runtime_payload_json,
                    storage_profile_json,
                    analysis_profile_json,
                    notes,
                    last_run_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_name = excluded.task_name,
                    platform = excluded.platform,
                    entity_type = excluded.entity_type,
                    task_mode = excluded.task_mode,
                    scenario_type = excluded.scenario_type,
                    status = excluded.status,
                    auth_profile_id = excluded.auth_profile_id,
                    task_payload_json = excluded.task_payload_json,
                    filter_payload_json = excluded.filter_payload_json,
                    runtime_payload_json = excluded.runtime_payload_json,
                    storage_profile_json = excluded.storage_profile_json,
                    analysis_profile_json = excluded.analysis_profile_json,
                    notes = excluded.notes,
                    last_run_at = excluded.last_run_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["task_name"],
                    payload["platform"],
                    payload["entity_type"],
                    payload["task_mode"],
                    payload["scenario_type"],
                    payload["status"],
                    payload.get("auth_profile_id"),
                    self._dump_json(payload.get("task_payload_json", {})),
                    self._dump_json(payload.get("filter_payload_json", {})),
                    self._dump_json(payload.get("runtime_payload_json", {})),
                    self._dump_json(payload.get("storage_profile_json", {})),
                    self._dump_json(payload.get("analysis_profile_json", {})),
                    payload.get("notes", ""),
                    payload.get("last_run_at"),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return task

    def delete_task(self, task_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM collection_tasks WHERE id = ?", (task_id,))
            connection.commit()
            return cursor.rowcount > 0

    def list_runs(self, task_id: str | None = None) -> list[TaskRun]:
        with self._connect() as connection:
            if task_id is None:
                rows = connection.execute("SELECT * FROM task_runs ORDER BY updated_at DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM task_runs WHERE task_id = ? ORDER BY updated_at DESC",
                    (task_id,),
                ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: str) -> TaskRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return self._row_to_run(row) if row is not None else None

    def save_run(self, run: TaskRun) -> TaskRun:
        payload = run.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_runs (
                    id,
                    task_id,
                    status,
                    trigger_type,
                    started_at,
                    finished_at,
                    log_path,
                    result_dataset_id,
                    result_dataset_ids,
                    error_message,
                    task_snapshot_json,
                    run_result_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    status = excluded.status,
                    trigger_type = excluded.trigger_type,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    log_path = excluded.log_path,
                    result_dataset_id = excluded.result_dataset_id,
                    result_dataset_ids = excluded.result_dataset_ids,
                    error_message = excluded.error_message,
                    task_snapshot_json = excluded.task_snapshot_json,
                    run_result_json = excluded.run_result_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["task_id"],
                    payload["status"],
                    payload.get("trigger_type", "manual"),
                    payload.get("started_at"),
                    payload.get("finished_at"),
                    payload.get("log_path", ""),
                    payload.get("result_dataset_id"),
                    self._dump_json(payload.get("result_dataset_ids", [])),
                    payload.get("error_message", ""),
                    self._dump_json(payload.get("task_snapshot_json", {})),
                    self._dump_json(payload.get("run_result_json", {})),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return run

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_tasks (
                    id TEXT PRIMARY KEY,
                    task_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    task_mode TEXT NOT NULL,
                    scenario_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    auth_profile_id TEXT,
                    task_payload_json TEXT NOT NULL DEFAULT '{}',
                    filter_payload_json TEXT NOT NULL DEFAULT '{}',
                    runtime_payload_json TEXT NOT NULL DEFAULT '{}',
                    storage_profile_json TEXT NOT NULL DEFAULT '{}',
                    analysis_profile_json TEXT NOT NULL DEFAULT '{}',
                    notes TEXT NOT NULL DEFAULT '',
                    last_run_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_platform ON collection_tasks (platform)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON collection_tasks (status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scenario ON collection_tasks (scenario_type)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger_type TEXT NOT NULL DEFAULT 'manual',
                    started_at TEXT,
                    finished_at TEXT,
                    log_path TEXT NOT NULL DEFAULT '',
                    result_dataset_id TEXT,
                    result_dataset_ids TEXT NOT NULL DEFAULT '[]',
                    error_message TEXT NOT NULL DEFAULT '',
                    task_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    run_result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON task_runs (task_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON task_runs (status)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_task(self, row: sqlite3.Row) -> CollectionTask:
        return CollectionTask.model_validate(
            {
                "id": row["id"],
                "task_name": row["task_name"],
                "platform": row["platform"],
                "entity_type": row["entity_type"],
                "task_mode": row["task_mode"],
                "scenario_type": row["scenario_type"],
                "status": row["status"],
                "auth_profile_id": row["auth_profile_id"],
                "task_payload_json": self._load_json_dict(row["task_payload_json"]),
                "filter_payload_json": self._load_json_dict(row["filter_payload_json"]),
                "runtime_payload_json": self._load_json_dict(row["runtime_payload_json"]),
                "storage_profile_json": self._load_json_dict(row["storage_profile_json"]),
                "analysis_profile_json": self._load_json_dict(row["analysis_profile_json"]),
                "notes": row["notes"],
                "last_run_at": row["last_run_at"],
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _row_to_run(self, row: sqlite3.Row) -> TaskRun:
        return TaskRun.model_validate(
            {
                "id": row["id"],
                "task_id": row["task_id"],
                "status": row["status"],
                "trigger_type": row["trigger_type"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "log_path": row["log_path"],
                "result_dataset_id": row["result_dataset_id"],
                "result_dataset_ids": self._load_json_list(row["result_dataset_ids"]),
                "error_message": row["error_message"],
                "task_snapshot_json": self._load_json_dict(row["task_snapshot_json"]),
                "run_result_json": self._load_json_dict(row["run_result_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _dump_json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _load_json_list(self, value: str) -> list[Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
