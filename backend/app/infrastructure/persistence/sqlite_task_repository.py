from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ...domain.models.platform import PlatformKey
from ...domain.models.task import (
    CollectionTask,
    EntityType,
    ScenarioType,
    TaskMode,
    TaskRun,
    TaskRunStatus,
    TaskStatus,
)
from ...domain.repositories.task_repository import CollectionTaskRepository


class SQLiteCollectionTaskRepository(CollectionTaskRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

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
        where_clause, parameters = self._task_filter_query(
            platform=platform,
            status=status,
            task_mode=task_mode,
            entity_type=entity_type,
            scenario_type=scenario_type,
            query=query,
        )
        statement = f"SELECT * FROM collection_tasks{where_clause} ORDER BY updated_at DESC"
        if limit is not None:
            statement += " LIMIT ?"
            parameters.append(limit)
        elif offset > 0:
            statement += " LIMIT -1"
        if offset > 0:
            statement += " OFFSET ?"
            parameters.append(offset)
        with self._connect() as connection:
            rows = connection.execute(statement, tuple(parameters)).fetchall()
        return [self._row_to_task(row) for row in rows]

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
        where_clause, parameters = self._task_filter_query(
            platform=platform,
            status=status,
            task_mode=task_mode,
            entity_type=entity_type,
            scenario_type=scenario_type,
            query=query,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM collection_tasks{where_clause}",
                tuple(parameters),
            ).fetchone()
        return int(row[0]) if row is not None else 0

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

    def list_runs(
        self,
        task_id: str | None = None,
        *,
        status: TaskRunStatus | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskRun]:
        where_clause, parameters = self._run_filter_query(task_id=task_id, status=status)
        statement = f"SELECT * FROM task_runs{where_clause} ORDER BY updated_at DESC"
        if limit is not None:
            statement += " LIMIT ?"
            parameters.append(limit)
        elif offset > 0:
            statement += " LIMIT -1"
        if offset > 0:
            statement += " OFFSET ?"
            parameters.append(offset)
        with self._connect() as connection:
            rows = connection.execute(statement, tuple(parameters)).fetchall()
        return [self._row_to_run(row) for row in rows]

    def count_runs(
        self,
        task_id: str | None = None,
        *,
        status: TaskRunStatus | None = None,
    ) -> int:
        where_clause, parameters = self._run_filter_query(task_id=task_id, status=status)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM task_runs{where_clause}",
                tuple(parameters),
            ).fetchone()
        return int(row[0]) if row is not None else 0

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

    @property
    def supports_run_leases(self) -> bool:
        return True

    def acquire_run_lease(
        self,
        task_id: str,
        run_id: str,
        owner_id: str,
        lease_seconds: float,
    ) -> bool:
        acquired_at = datetime.utcnow()
        expires_at = acquired_at + timedelta(seconds=max(1.0, lease_seconds))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM task_run_leases WHERE expires_at <= ?",
                (acquired_at.isoformat(),),
            )
            cursor = connection.execute(
                """
                INSERT INTO task_run_leases (
                    task_id,
                    run_id,
                    owner_id,
                    acquired_at,
                    renewed_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    run_id = excluded.run_id,
                    owner_id = excluded.owner_id,
                    acquired_at = excluded.acquired_at,
                    renewed_at = excluded.renewed_at,
                    expires_at = excluded.expires_at
                WHERE task_run_leases.expires_at <= excluded.acquired_at
                   OR (
                       task_run_leases.run_id = excluded.run_id
                       AND task_run_leases.owner_id = excluded.owner_id
                   )
                """,
                (
                    task_id,
                    run_id,
                    owner_id,
                    acquired_at.isoformat(),
                    acquired_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()
            return cursor.rowcount > 0

    def renew_run_lease(
        self,
        task_id: str,
        run_id: str,
        owner_id: str,
        lease_seconds: float,
    ) -> bool:
        renewed_at = datetime.utcnow()
        expires_at = renewed_at + timedelta(seconds=max(1.0, lease_seconds))
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE task_run_leases
                SET renewed_at = ?, expires_at = ?
                WHERE task_id = ?
                  AND run_id = ?
                  AND owner_id = ?
                  AND expires_at > ?
                """,
                (
                    renewed_at.isoformat(),
                    expires_at.isoformat(),
                    task_id,
                    run_id,
                    owner_id,
                    renewed_at.isoformat(),
                ),
            )
            connection.commit()
            return cursor.rowcount > 0

    def release_run_lease(self, task_id: str, run_id: str, owner_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM task_run_leases
                WHERE task_id = ? AND run_id = ? AND owner_id = ?
                """,
                (task_id, run_id, owner_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def is_run_lease_active(self, task_id: str, run_id: str) -> bool:
        current = datetime.utcnow().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM task_run_leases
                WHERE task_id = ? AND run_id = ? AND expires_at > ?
                """,
                (task_id, run_id, current),
            ).fetchone()
        return row is not None

    def count_active_run_leases(self) -> int:
        current = datetime.utcnow().isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM task_run_leases WHERE expires_at <= ?", (current,))
            row = connection.execute("SELECT COUNT(*) FROM task_run_leases").fetchone()
            connection.commit()
        return int(row[0]) if row is not None else 0

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
            connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON collection_tasks (updated_at DESC)")
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
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_task_updated ON task_runs (task_id, updated_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_run_leases (
                    task_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    owner_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    renewed_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_run_leases_expires ON task_run_leases (expires_at)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _run_filter_query(
        self,
        *,
        task_id: str | None,
        status: TaskRunStatus | None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if task_id is not None:
            clauses.append("task_id = ?")
            parameters.append(task_id)
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)
        return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), parameters

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

    def _task_filter_query(
        self,
        *,
        platform: PlatformKey | None,
        status: TaskStatus | None,
        task_mode: TaskMode | None,
        entity_type: EntityType | None,
        scenario_type: ScenarioType | None,
        query: str,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        enum_filters = (
            ("platform", platform),
            ("status", status),
            ("task_mode", task_mode),
            ("entity_type", entity_type),
            ("scenario_type", scenario_type),
        )
        for column, value in enum_filters:
            if value:
                clauses.append(f"{column} = ?")
                parameters.append(value.value)
        needle = query.strip().lower()
        if needle:
            scalar_values = (
                "id",
                "task_name",
                "platform",
                "entity_type",
                "task_mode",
                "scenario_type",
                "status",
                "notes",
                "auth_profile_id",
            )
            query_clauses = [
                *(f"lower(coalesce({value}, '')) LIKE ? ESCAPE '\\'" for value in scalar_values),
                (
                    "EXISTS (SELECT 1 FROM json_each(collection_tasks.task_payload_json) "
                    "WHERE lower(CAST(value AS TEXT)) LIKE ? ESCAPE '\\')"
                ),
            ]
            clauses.append(f"({' OR '.join(query_clauses)})")
            parameters.extend([self._like_value(needle)] * len(query_clauses))
        return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), parameters

    def _like_value(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

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
