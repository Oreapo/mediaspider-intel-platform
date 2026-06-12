from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.signal import RiskLevel, Signal, SignalStatus, SignalType
from ...domain.repositories.signal_repository import SignalRepository


class SQLiteSignalRepository(SignalRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_signals(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Signal]:
        where_clause, parameters = self._filter_query(
            dataset_id=dataset_id,
            status=status,
            risk_level=risk_level,
            signal_type=signal_type,
            query=query,
        )
        statement = f"SELECT * FROM signals{where_clause} ORDER BY updated_at DESC"
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
        return [self._row_to_signal(row) for row in rows]

    def count_signals(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
    ) -> int:
        where_clause, parameters = self._filter_query(
            dataset_id=dataset_id,
            status=status,
            risk_level=risk_level,
            signal_type=signal_type,
            query=query,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM signals{where_clause}",
                tuple(parameters),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def get_signal(self, signal_id: str) -> Signal | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
        return self._row_to_signal(row) if row is not None else None

    def save_signal(self, signal: Signal) -> Signal:
        payload = signal.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO signals (
                    id,
                    dataset_id,
                    task_run_id,
                    signal_type,
                    signal_source,
                    risk_level,
                    risk_score,
                    summary,
                    payload_json,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    task_run_id = excluded.task_run_id,
                    signal_type = excluded.signal_type,
                    signal_source = excluded.signal_source,
                    risk_level = excluded.risk_level,
                    risk_score = excluded.risk_score,
                    summary = excluded.summary,
                    payload_json = excluded.payload_json,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["dataset_id"],
                    payload.get("task_run_id"),
                    payload["signal_type"],
                    payload["signal_source"],
                    payload["risk_level"],
                    payload["risk_score"],
                    payload["summary"],
                    json.dumps(payload.get("payload_json", {}), ensure_ascii=False, sort_keys=True),
                    payload["status"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return signal

    def delete_signal(self, signal_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM signals WHERE id = ?", (signal_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    task_run_id TEXT,
                    signal_type TEXT NOT NULL,
                    signal_source TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_dataset_id ON signals (dataset_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_task_run_id ON signals (task_run_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_type ON signals (signal_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_risk_level ON signals (risk_level)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals (status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_signals_updated_at ON signals (updated_at DESC)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_signal(self, row: sqlite3.Row) -> Signal:
        return Signal.model_validate(
            {
                "id": row["id"],
                "dataset_id": row["dataset_id"],
                "task_run_id": row["task_run_id"],
                "signal_type": row["signal_type"],
                "signal_source": row["signal_source"],
                "risk_level": row["risk_level"],
                "risk_score": row["risk_score"],
                "summary": row["summary"],
                "payload_json": self._load_json_dict(row["payload_json"]),
                "status": row["status"],
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _filter_query(
        self,
        *,
        dataset_id: str | None,
        status: SignalStatus | None,
        risk_level: RiskLevel | None,
        signal_type: SignalType | None,
        query: str,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if dataset_id:
            clauses.append("dataset_id = ?")
            parameters.append(dataset_id)
        if status:
            clauses.append("status = ?")
            parameters.append(status.value)
        if risk_level:
            clauses.append("risk_level = ?")
            parameters.append(risk_level.value)
        if signal_type:
            clauses.append("signal_type = ?")
            parameters.append(signal_type.value)
        needle = query.strip().lower()
        if needle:
            searchable_values = (
                "id",
                "dataset_id",
                "signal_type",
                "signal_source",
                "risk_level",
                "status",
                "summary",
                "json_extract(payload_json, '$.source_ref')",
            )
            clauses.append(
                "("
                + " OR ".join(f"lower(coalesce({value}, '')) LIKE ? ESCAPE '\\'" for value in searchable_values)
                + ")"
            )
            parameters.extend([self._like_value(needle)] * len(searchable_values))
        return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), parameters

    def _like_value(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
