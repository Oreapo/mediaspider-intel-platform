from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


COLLECTION_FILES = {
    "collection_tasks": "collection_tasks.json",
    "task_runs": "task_runs.json",
    "datasets": "datasets.json",
    "analysis_jobs": "analysis_jobs.json",
    "analysis_outputs": "analysis_outputs.json",
    "signals": "signals.json",
    "risk_entities": "risk_entities.json",
    "entity_relations": "entity_relations.json",
    "cases": "cases.json",
    "case_links": "case_links.json",
    "case_notes": "case_notes.json",
    "evidence_packets": "evidence_packets.json",
    "reports": "reports.json",
    "notification_rules": "notification_rules.json",
    "notification_deliveries": "notification_deliveries.json",
    "platform_profiles": "platform_profiles.json",
}


@dataclass(frozen=True)
class MigrationCollectionResult:
    collection: str
    source_file: str
    imported_count: int
    skipped_count: int


@dataclass(frozen=True)
class MigrationResult:
    sqlite_path: str
    storage_dir: str
    started_at: str
    finished_at: str
    collections: list[MigrationCollectionResult]

    @property
    def imported_count(self) -> int:
        return sum(item.imported_count for item in self.collections)

    @property
    def skipped_count(self) -> int:
        return sum(item.skipped_count for item in self.collections)


class JsonToSQLiteMigrator:
    def __init__(self, storage_dir: Path, sqlite_path: Path):
        self.storage_dir = storage_dir
        self.sqlite_path = sqlite_path

    def run(self) -> MigrationResult:
        started_at = datetime.utcnow().isoformat()
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as connection:
            self._create_schema(connection)
            results = [
                self._import_collection(connection, collection, file_name)
                for collection, file_name in COLLECTION_FILES.items()
            ]
            connection.commit()
        finished_at = datetime.utcnow().isoformat()
        return MigrationResult(
            sqlite_path=str(self.sqlite_path),
            storage_dir=str(self.storage_dir),
            started_at=started_at,
            finished_at=finished_at,
            collections=results,
        )

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS json_records (
                collection TEXT NOT NULL,
                record_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                migrated_at TEXT NOT NULL,
                PRIMARY KEY (collection, record_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_json_records_collection_updated
            ON json_records (collection, updated_at)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS migration_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                storage_dir TEXT NOT NULL,
                sqlite_path TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                imported_count INTEGER NOT NULL,
                skipped_count INTEGER NOT NULL
            )
            """
        )

    def _import_collection(
        self,
        connection: sqlite3.Connection,
        collection: str,
        file_name: str,
    ) -> MigrationCollectionResult:
        source_file = self.storage_dir / file_name
        records = self._load_records(source_file)
        imported_count = 0
        skipped_count = 0
        migrated_at = datetime.utcnow().isoformat()

        for index, record in enumerate(records):
            record_id = self._record_id(collection, record, index)
            if not record_id:
                skipped_count += 1
                continue
            connection.execute(
                """
                INSERT INTO json_records (
                    collection,
                    record_id,
                    payload_json,
                    created_at,
                    updated_at,
                    migrated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection, record_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    migrated_at = excluded.migrated_at
                """,
                (
                    collection,
                    record_id,
                    json.dumps(record, ensure_ascii=False, sort_keys=True),
                    self._string_or_none(record.get("created_at")),
                    self._string_or_none(record.get("updated_at")),
                    migrated_at,
                ),
            )
            imported_count += 1

        return MigrationCollectionResult(
            collection=collection,
            source_file=str(source_file),
            imported_count=imported_count,
            skipped_count=skipped_count,
        )

    def _load_records(self, source_file: Path) -> list[dict[str, Any]]:
        if not source_file.exists():
            return []
        try:
            raw = json.loads(source_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _record_id(self, collection: str, record: dict[str, Any], index: int) -> str:
        value = record.get("id")
        if value is not None and str(value).strip():
            return str(value)
        return f"{collection}:{index}"

    def _string_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        return str(value)


def persist_migration_run(result: MigrationResult) -> None:
    with sqlite3.connect(result.sqlite_path) as connection:
        connection.execute(
            """
            INSERT INTO migration_runs (
                storage_dir,
                sqlite_path,
                started_at,
                finished_at,
                imported_count,
                skipped_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result.storage_dir,
                result.sqlite_path,
                result.started_at,
                result.finished_at,
                result.imported_count,
                result.skipped_count,
            ),
        )
        connection.commit()
