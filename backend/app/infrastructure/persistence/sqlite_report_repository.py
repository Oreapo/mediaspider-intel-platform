from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.report import Report
from ...domain.repositories.report_repository import ReportRepository


class SQLiteReportRepository(ReportRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_reports(self) -> list[Report]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM reports ORDER BY updated_at DESC").fetchall()
        return [self._row_to_report(row) for row in rows]

    def get_report(self, report_id: str) -> Report | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return self._row_to_report(row) if row is not None else None

    def save_report(self, report: Report) -> Report:
        payload = report.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reports (
                    id,
                    case_id,
                    report_name,
                    report_type,
                    status,
                    storage_uri,
                    content_markdown,
                    summary_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id = excluded.case_id,
                    report_name = excluded.report_name,
                    report_type = excluded.report_type,
                    status = excluded.status,
                    storage_uri = excluded.storage_uri,
                    content_markdown = excluded.content_markdown,
                    summary_json = excluded.summary_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["case_id"],
                    payload["report_name"],
                    payload["report_type"],
                    payload["status"],
                    payload["storage_uri"],
                    payload["content_markdown"],
                    json.dumps(payload.get("summary_json", {}), ensure_ascii=False, sort_keys=True),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return report

    def delete_report(self, report_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    report_name TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    storage_uri TEXT NOT NULL DEFAULT '',
                    content_markdown TEXT NOT NULL DEFAULT '',
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_case_id ON reports (case_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_type ON reports (report_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (status)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_report(self, row: sqlite3.Row) -> Report:
        return Report.model_validate(
            {
                "id": row["id"],
                "case_id": row["case_id"],
                "report_name": row["report_name"],
                "report_type": row["report_type"],
                "status": row["status"],
                "storage_uri": row["storage_uri"],
                "content_markdown": row["content_markdown"],
                "summary_json": self._load_json_dict(row["summary_json"]),
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
