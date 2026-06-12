from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.audit import AuditEvent
from ...domain.repositories.audit_repository import AuditRepository


class SQLiteAuditRepository(AuditRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_events(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_username: str | None = None,
        action: str | None = None,
        query: str = "",
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[AuditEvent]:
        where_clause, params = self._filter_query(
            target_type=target_type,
            target_id=target_id,
            actor_username=actor_username,
            action=action,
            query=query,
            created_from=created_from,
            created_to=created_to,
        )
        statement = f"SELECT * FROM audit_events{where_clause} ORDER BY created_at DESC"
        if limit is not None:
            statement += " LIMIT ?"
            params.append(limit)
        elif offset:
            statement += " LIMIT -1"
        if offset:
            statement += " OFFSET ?"
            params.append(offset)
        with self._connect() as connection:
            rows = connection.execute(statement, tuple(params)).fetchall()
        return [self._row_to_event(row) for row in rows]

    def count_events(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_username: str | None = None,
        action: str | None = None,
        query: str = "",
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        where_clause, params = self._filter_query(
            target_type=target_type,
            target_id=target_id,
            actor_username=actor_username,
            action=action,
            query=query,
            created_from=created_from,
            created_to=created_to,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS total FROM audit_events{where_clause}",
                tuple(params),
            ).fetchone()
        return int(row["total"]) if row is not None else 0

    def save_event(self, event: AuditEvent) -> AuditEvent:
        payload = event.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    id,
                    action,
                    actor_username,
                    actor_role,
                    target_type,
                    target_id,
                    summary,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    action = excluded.action,
                    actor_username = excluded.actor_username,
                    actor_role = excluded.actor_role,
                    target_type = excluded.target_type,
                    target_id = excluded.target_id,
                    summary = excluded.summary,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["action"],
                    payload["actor_username"],
                    payload["actor_role"],
                    payload["target_type"],
                    payload["target_id"],
                    payload["summary"],
                    json.dumps(payload.get("metadata_json", {}), ensure_ascii=False, sort_keys=True),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return event

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    actor_username TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_events (target_type, target_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events (actor_username)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_events (created_at)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _filter_query(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_username: str | None = None,
        action: str | None = None,
        query: str = "",
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id:
            clauses.append("target_id = ?")
            params.append(target_id)
        if actor_username:
            clauses.append("actor_username = ?")
            params.append(actor_username)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)
        normalized_query = query.strip().lower()
        if normalized_query:
            clauses.append(
                "(lower(id) LIKE ? OR lower(action) LIKE ? OR lower(actor_username) LIKE ? OR lower(actor_role) LIKE ? OR lower(target_type) LIKE ? OR lower(target_id) LIKE ? OR lower(summary) LIKE ? OR lower(metadata_json) LIKE ?)"
            )
            like = f"%{normalized_query}%"
            params.extend([like, like, like, like, like, like, like, like])
        return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params

    def _row_to_event(self, row: sqlite3.Row) -> AuditEvent:
        return AuditEvent.model_validate(
            {
                "id": row["id"],
                "action": row["action"],
                "actor_username": row["actor_username"],
                "actor_role": row["actor_role"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "summary": row["summary"],
                "metadata_json": self._load_json_dict(row["metadata_json"]),
                "created_at": datetime.fromisoformat(row["created_at"]),
                "updated_at": datetime.fromisoformat(row["updated_at"]),
            }
        )

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
