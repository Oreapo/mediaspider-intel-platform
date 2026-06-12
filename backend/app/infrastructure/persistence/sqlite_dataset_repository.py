from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.dataset import Dataset, DatasetType
from ...domain.models.platform import PlatformKey
from ...domain.models.task import ScenarioType
from ...domain.repositories.dataset_repository import DatasetRepository


class SQLiteDatasetRepository(DatasetRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_datasets(
        self,
        *,
        source_platform: PlatformKey | None = None,
        dataset_type: DatasetType | None = None,
        scenario_type: ScenarioType | None = None,
        tag: str = "",
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Dataset]:
        where_clause, parameters = self._filter_query(
            source_platform=source_platform,
            dataset_type=dataset_type,
            scenario_type=scenario_type,
            tag=tag,
            query=query,
        )
        statement = f"SELECT * FROM datasets{where_clause} ORDER BY updated_at DESC"
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
        return [self._row_to_dataset(row) for row in rows]

    def count_datasets(
        self,
        *,
        source_platform: PlatformKey | None = None,
        dataset_type: DatasetType | None = None,
        scenario_type: ScenarioType | None = None,
        tag: str = "",
        query: str = "",
    ) -> int:
        where_clause, parameters = self._filter_query(
            source_platform=source_platform,
            dataset_type=dataset_type,
            scenario_type=scenario_type,
            tag=tag,
            query=query,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM datasets{where_clause}",
                tuple(parameters),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM datasets WHERE id = ?",
                (dataset_id,),
            ).fetchone()
        return self._row_to_dataset(row) if row is not None else None

    def save_dataset(self, dataset: Dataset) -> Dataset:
        payload = dataset.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO datasets (
                    id,
                    dataset_name,
                    dataset_type,
                    source_platform,
                    source_task_id,
                    source_run_id,
                    scenario_type,
                    record_count,
                    storage_uri,
                    schema_version,
                    snapshot_time,
                    tags_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    dataset_name = excluded.dataset_name,
                    dataset_type = excluded.dataset_type,
                    source_platform = excluded.source_platform,
                    source_task_id = excluded.source_task_id,
                    source_run_id = excluded.source_run_id,
                    scenario_type = excluded.scenario_type,
                    record_count = excluded.record_count,
                    storage_uri = excluded.storage_uri,
                    schema_version = excluded.schema_version,
                    snapshot_time = excluded.snapshot_time,
                    tags_json = excluded.tags_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["dataset_name"],
                    payload["dataset_type"],
                    payload["source_platform"],
                    payload.get("source_task_id"),
                    payload.get("source_run_id"),
                    payload.get("scenario_type"),
                    payload["record_count"],
                    payload["storage_uri"],
                    payload["schema_version"],
                    payload.get("snapshot_time"),
                    json.dumps(payload.get("tags", []), ensure_ascii=False),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return dataset

    def delete_dataset(self, dataset_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    dataset_type TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    source_task_id TEXT,
                    source_run_id TEXT,
                    scenario_type TEXT,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    storage_uri TEXT NOT NULL DEFAULT '',
                    schema_version TEXT NOT NULL DEFAULT 'v1',
                    snapshot_time TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_datasets_source_platform ON datasets (source_platform)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_datasets_scenario_type ON datasets (scenario_type)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_datasets_updated_at ON datasets (updated_at DESC)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_dataset(self, row: sqlite3.Row) -> Dataset:
        return Dataset.model_validate(
            {
                "id": row["id"],
                "dataset_name": row["dataset_name"],
                "dataset_type": row["dataset_type"],
                "source_platform": row["source_platform"],
                "source_task_id": row["source_task_id"],
                "source_run_id": row["source_run_id"],
                "scenario_type": row["scenario_type"],
                "record_count": row["record_count"],
                "storage_uri": row["storage_uri"],
                "schema_version": row["schema_version"],
                "snapshot_time": row["snapshot_time"],
                "tags": self._load_json_list(row["tags_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _filter_query(
        self,
        *,
        source_platform: PlatformKey | None,
        dataset_type: DatasetType | None,
        scenario_type: ScenarioType | None,
        tag: str,
        query: str,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if source_platform:
            clauses.append("source_platform = ?")
            parameters.append(source_platform.value)
        if dataset_type:
            clauses.append("dataset_type = ?")
            parameters.append(dataset_type.value)
        if scenario_type:
            clauses.append("scenario_type = ?")
            parameters.append(scenario_type.value)
        tag_needle = tag.strip().lower()
        if tag_needle:
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(datasets.tags_json) WHERE lower(CAST(value AS TEXT)) LIKE ? ESCAPE '\\')"
            )
            parameters.append(self._like_value(tag_needle))
        query_needle = query.strip().lower()
        if query_needle:
            searchable_columns = (
                "id",
                "dataset_name",
                "dataset_type",
                "source_platform",
                "scenario_type",
                "storage_uri",
                "schema_version",
                "source_task_id",
                "source_run_id",
                "tags_json",
            )
            clauses.append(
                "("
                + " OR ".join(f"lower(coalesce({column}, '')) LIKE ? ESCAPE '\\'" for column in searchable_columns)
                + ")"
            )
            parameters.extend([self._like_value(query_needle)] * len(searchable_columns))
        return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), parameters

    def _like_value(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def _load_json_list(self, value: str) -> list[Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
