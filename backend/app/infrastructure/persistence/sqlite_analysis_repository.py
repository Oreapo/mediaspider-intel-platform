from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.analysis import AnalysisJob, AnalysisOutput
from ...domain.repositories.analysis_repository import AnalysisRepository


class SQLiteAnalysisRepository(AnalysisRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_jobs(self, *, limit: int | None = None, offset: int = 0) -> list[AnalysisJob]:
        statement = "SELECT * FROM analysis_jobs ORDER BY updated_at DESC"
        parameters: list[int] = []
        if limit is not None:
            statement += " LIMIT ?"
            parameters.append(limit)
        elif offset > 0:
            statement += " LIMIT -1"
        if offset > 0:
            statement += " OFFSET ?"
            parameters.append(offset)
        with self._connect() as connection:
            rows = connection.execute(statement, parameters).fetchall()
        return [self._row_to_job(row) for row in rows]

    def count_jobs(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM analysis_jobs").fetchone()
        return int(row[0]) if row is not None else 0

    def get_job(self, job_id: str) -> AnalysisJob | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM analysis_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row is not None else None

    def save_job(self, job: AnalysisJob) -> AnalysisJob:
        payload = job.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_jobs (
                    id,
                    dataset_id,
                    analysis_scope,
                    analysis_type,
                    status,
                    parameters_json,
                    started_at,
                    finished_at,
                    error_message,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    analysis_scope = excluded.analysis_scope,
                    analysis_type = excluded.analysis_type,
                    status = excluded.status,
                    parameters_json = excluded.parameters_json,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    error_message = excluded.error_message,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["dataset_id"],
                    payload["analysis_scope"],
                    payload["analysis_type"],
                    payload["status"],
                    json.dumps(payload.get("parameters_json", {}), ensure_ascii=False, sort_keys=True),
                    payload.get("started_at"),
                    payload.get("finished_at"),
                    payload["error_message"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return job

    def list_outputs(self, job_id: str) -> list[AnalysisOutput]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analysis_outputs WHERE analysis_job_id = ? ORDER BY updated_at DESC",
                (job_id,),
            ).fetchall()
        return [self._row_to_output(row) for row in rows]

    def save_output(self, output: AnalysisOutput) -> AnalysisOutput:
        payload = output.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_outputs (
                    id,
                    analysis_job_id,
                    output_type,
                    title,
                    summary,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    analysis_job_id = excluded.analysis_job_id,
                    output_type = excluded.output_type,
                    title = excluded.title,
                    summary = excluded.summary,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["analysis_job_id"],
                    payload["output_type"],
                    payload["title"],
                    payload["summary"],
                    json.dumps(payload.get("payload_json", {}), ensure_ascii=False, sort_keys=True),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return output

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    analysis_scope TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT,
                    finished_at TEXT,
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_outputs (
                    id TEXT PRIMARY KEY,
                    analysis_job_id TEXT NOT NULL,
                    output_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_dataset_id ON analysis_jobs (dataset_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status ON analysis_jobs (status)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_jobs_updated_at ON analysis_jobs (updated_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_outputs_job_id ON analysis_outputs (analysis_job_id)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_job(self, row: sqlite3.Row) -> AnalysisJob:
        return AnalysisJob.model_validate(
            {
                "id": row["id"],
                "dataset_id": row["dataset_id"],
                "analysis_scope": row["analysis_scope"],
                "analysis_type": row["analysis_type"],
                "status": row["status"],
                "parameters_json": self._load_json_dict(row["parameters_json"]),
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "error_message": row["error_message"],
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _row_to_output(self, row: sqlite3.Row) -> AnalysisOutput:
        return AnalysisOutput.model_validate(
            {
                "id": row["id"],
                "analysis_job_id": row["analysis_job_id"],
                "output_type": row["output_type"],
                "title": row["title"],
                "summary": row["summary"],
                "payload_json": self._load_json_dict(row["payload_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
