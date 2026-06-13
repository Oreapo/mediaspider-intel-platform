from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.case import Case, CaseLink, CaseNote, CasePriority, CaseStatus
from ...domain.repositories.case_repository import CaseRepository


class SQLiteCaseRepository(CaseRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_cases(
        self,
        *,
        status: CaseStatus | None = None,
        priority: CasePriority | None = None,
        case_type: str = "",
        owner: str = "",
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Case]:
        where_clause, parameters = self._case_filter_query(
            status=status,
            priority=priority,
            case_type=case_type,
            owner=owner,
            query=query,
        )
        statement = f"SELECT * FROM cases{where_clause} ORDER BY updated_at DESC"
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
        return [self._row_to_case(row) for row in rows]

    def count_cases(
        self,
        *,
        status: CaseStatus | None = None,
        priority: CasePriority | None = None,
        case_type: str = "",
        owner: str = "",
        query: str = "",
    ) -> int:
        where_clause, parameters = self._case_filter_query(
            status=status,
            priority=priority,
            case_type=case_type,
            owner=owner,
            query=query,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM cases{where_clause}",
                tuple(parameters),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def get_case(self, case_id: str) -> Case | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return self._row_to_case(row) if row is not None else None

    def save_case(self, case: Case) -> Case:
        payload = case.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cases (
                    id,
                    case_name,
                    case_type,
                    status,
                    priority,
                    summary,
                    owner,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_name = excluded.case_name,
                    case_type = excluded.case_type,
                    status = excluded.status,
                    priority = excluded.priority,
                    summary = excluded.summary,
                    owner = excluded.owner,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["case_name"],
                    payload["case_type"],
                    payload["status"],
                    payload["priority"],
                    payload["summary"],
                    payload["owner"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return case

    def delete_case(self, case_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            if cursor.rowcount > 0:
                connection.execute("DELETE FROM case_links WHERE case_id = ?", (case_id,))
                connection.execute("DELETE FROM case_notes WHERE case_id = ?", (case_id,))
            connection.commit()
            return cursor.rowcount > 0

    def list_links(self, case_id: str | None = None) -> list[CaseLink]:
        with self._connect() as connection:
            if case_id is None:
                rows = connection.execute("SELECT * FROM case_links ORDER BY created_at ASC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM case_links WHERE case_id = ? ORDER BY created_at ASC",
                    (case_id,),
                ).fetchall()
        return [self._row_to_link(row) for row in rows]

    def save_link(self, link: CaseLink) -> CaseLink:
        payload = link.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO case_links (
                    id,
                    case_id,
                    link_type,
                    target_id,
                    label,
                    source_ref_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id = excluded.case_id,
                    link_type = excluded.link_type,
                    target_id = excluded.target_id,
                    label = excluded.label,
                    source_ref_json = excluded.source_ref_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["case_id"],
                    payload["link_type"],
                    payload["target_id"],
                    payload["label"],
                    self._dump_json(payload.get("source_ref_json", {})),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return link

    def delete_link(self, link_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM case_links WHERE id = ?", (link_id,))
            connection.commit()
            return cursor.rowcount > 0

    def list_notes(self, case_id: str | None = None) -> list[CaseNote]:
        with self._connect() as connection:
            if case_id is None:
                rows = connection.execute("SELECT * FROM case_notes ORDER BY created_at ASC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at ASC",
                    (case_id,),
                ).fetchall()
        return [self._row_to_note(row) for row in rows]

    def save_note(self, note: CaseNote) -> CaseNote:
        payload = note.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO case_notes (
                    id,
                    case_id,
                    author,
                    body,
                    note_type,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id = excluded.case_id,
                    author = excluded.author,
                    body = excluded.body,
                    note_type = excluded.note_type,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["case_id"],
                    payload["author"],
                    payload["body"],
                    payload["note_type"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return note

    def delete_note(self, note_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM case_notes WHERE id = ?", (note_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    case_name TEXT NOT NULL,
                    case_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cases_type ON cases (case_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases (status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cases_priority ON cases (priority)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON cases (updated_at DESC)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS case_links (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    source_ref_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_case_links_case_id ON case_links (case_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_case_links_target ON case_links (link_type, target_id)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS case_notes (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    author TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL,
                    note_type TEXT NOT NULL DEFAULT 'investigation',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_case_notes_case_id ON case_notes (case_id)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_case(self, row: sqlite3.Row) -> Case:
        return Case.model_validate(
            {
                "id": row["id"],
                "case_name": row["case_name"],
                "case_type": row["case_type"],
                "status": row["status"],
                "priority": row["priority"],
                "summary": row["summary"],
                "owner": row["owner"],
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _row_to_link(self, row: sqlite3.Row) -> CaseLink:
        return CaseLink.model_validate(
            {
                "id": row["id"],
                "case_id": row["case_id"],
                "link_type": row["link_type"],
                "target_id": row["target_id"],
                "label": row["label"],
                "source_ref_json": self._load_json_dict(row["source_ref_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _row_to_note(self, row: sqlite3.Row) -> CaseNote:
        return CaseNote.model_validate(
            {
                "id": row["id"],
                "case_id": row["case_id"],
                "author": row["author"],
                "body": row["body"],
                "note_type": row["note_type"],
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _case_filter_query(
        self,
        *,
        status: CaseStatus | None,
        priority: CasePriority | None,
        case_type: str,
        owner: str,
        query: str,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if status:
            clauses.append("status = ?")
            parameters.append(status.value)
        if priority:
            clauses.append("priority = ?")
            parameters.append(priority.value)
        if case_type:
            clauses.append("case_type = ?")
            parameters.append(case_type)
        owner_needle = owner.strip().lower()
        if owner_needle:
            clauses.append("lower(owner) LIKE ? ESCAPE '\\'")
            parameters.append(self._like_value(owner_needle))
        query_needle = query.strip().lower()
        if query_needle:
            searchable_columns = (
                "id",
                "case_name",
                "case_type",
                "status",
                "priority",
                "summary",
                "owner",
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

    def _dump_json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
