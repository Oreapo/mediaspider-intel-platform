from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ...domain.models.analysis import AnalysisJob, AnalysisOutput
from ...domain.models.audit import AuditEvent
from ...domain.models.case import Case, CaseLink, CaseNote
from ...domain.models.dataset import Dataset
from ...domain.models.entity import EntityRelation, RiskEntity
from ...domain.models.evidence import EvidencePacket
from ...domain.models.notification import NotificationDelivery, NotificationRule
from ...domain.models.platform import PlatformProfile
from ...domain.models.report import Report
from ...domain.models.signal import Signal
from ...domain.models.task import CollectionTask, TaskRun
from .sqlite_analysis_repository import SQLiteAnalysisRepository
from .sqlite_audit_repository import SQLiteAuditRepository
from .sqlite_case_repository import SQLiteCaseRepository
from .sqlite_dataset_repository import SQLiteDatasetRepository
from .sqlite_entity_repository import SQLiteEntityRepository
from .sqlite_evidence_repository import SQLiteEvidenceRepository
from .sqlite_notification_repository import SQLiteNotificationRepository
from .sqlite_platform_profile_repository import SQLitePlatformProfileRepository
from .sqlite_report_repository import SQLiteReportRepository
from .sqlite_signal_repository import SQLiteSignalRepository
from .sqlite_task_repository import SQLiteCollectionTaskRepository

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
    "audit_events": "audit_events.json",
}


@dataclass(frozen=True)
class MigrationCollectionResult:
    collection: str
    source_file: str
    imported_count: int
    skipped_count: int
    native_imported_count: int = 0
    native_skipped_count: int = 0


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

    @property
    def native_imported_count(self) -> int:
        return sum(item.native_imported_count for item in self.collections)

    @property
    def native_skipped_count(self) -> int:
        return sum(item.native_skipped_count for item in self.collections)


class JsonToSQLiteMigrator:
    def __init__(self, storage_dir: Path, sqlite_path: Path, *, activate_native: bool = True):
        self.storage_dir = storage_dir
        self.sqlite_path = sqlite_path
        self.activate_native = activate_native

    def run(self) -> MigrationResult:
        started_at = datetime.utcnow().isoformat()
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.sqlite_path)) as connection:
            self._create_schema(connection)
            results = [
                self._import_collection(connection, collection, file_name)
                for collection, file_name in COLLECTION_FILES.items()
            ]
            connection.commit()
        if self.activate_native:
            native_results = self._activate_native_collections()
            results = [
                replace(
                    item,
                    native_imported_count=native_results[item.collection][0],
                    native_skipped_count=native_results[item.collection][1],
                )
                for item in results
            ]
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
                skipped_count INTEGER NOT NULL,
                native_imported_count INTEGER NOT NULL DEFAULT 0,
                native_skipped_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._ensure_column(connection, "migration_runs", "native_imported_count", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column(connection, "migration_runs", "native_skipped_count", "INTEGER NOT NULL DEFAULT 0")

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

    def _activate_native_collections(self) -> dict[str, tuple[int, int]]:
        specs = self._native_import_specs()
        results: dict[str, tuple[int, int]] = {}
        for collection, file_name in COLLECTION_FILES.items():
            model_type, save_record = specs[collection]
            imported_count = 0
            skipped_count = 0
            for record in self._load_records(self.storage_dir / file_name):
                if not str(record.get("id") or "").strip():
                    skipped_count += 1
                    continue
                try:
                    save_record(model_type.model_validate(record))
                except Exception:
                    skipped_count += 1
                    continue
                imported_count += 1
            results[collection] = (imported_count, skipped_count)
        return results

    def _native_import_specs(self) -> dict[str, tuple[type, Callable[[Any], Any]]]:
        task_repository = SQLiteCollectionTaskRepository(self.sqlite_path)
        dataset_repository = SQLiteDatasetRepository(self.sqlite_path)
        analysis_repository = SQLiteAnalysisRepository(self.sqlite_path)
        signal_repository = SQLiteSignalRepository(self.sqlite_path)
        entity_repository = SQLiteEntityRepository(self.sqlite_path)
        case_repository = SQLiteCaseRepository(self.sqlite_path)
        evidence_repository = SQLiteEvidenceRepository(self.sqlite_path)
        report_repository = SQLiteReportRepository(self.sqlite_path)
        notification_repository = SQLiteNotificationRepository(self.sqlite_path)
        profile_repository = SQLitePlatformProfileRepository(self.sqlite_path)
        audit_repository = SQLiteAuditRepository(self.sqlite_path)
        return {
            "collection_tasks": (CollectionTask, task_repository.save_task),
            "task_runs": (TaskRun, task_repository.save_run),
            "datasets": (Dataset, dataset_repository.save_dataset),
            "analysis_jobs": (AnalysisJob, analysis_repository.save_job),
            "analysis_outputs": (AnalysisOutput, analysis_repository.save_output),
            "signals": (Signal, signal_repository.save_signal),
            "risk_entities": (RiskEntity, entity_repository.save_entity),
            "entity_relations": (EntityRelation, entity_repository.save_relation),
            "cases": (Case, case_repository.save_case),
            "case_links": (CaseLink, case_repository.save_link),
            "case_notes": (CaseNote, case_repository.save_note),
            "evidence_packets": (EvidencePacket, evidence_repository.save_packet),
            "reports": (Report, report_repository.save_report),
            "notification_rules": (NotificationRule, notification_repository.save_rule),
            "notification_deliveries": (NotificationDelivery, notification_repository.save_delivery),
            "platform_profiles": (PlatformProfile, profile_repository.save_profile),
            "audit_events": (AuditEvent, audit_repository.save_event),
        }

    def _ensure_column(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

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


def persist_migration_run(result: MigrationResult, *, database_path: Path | str | None = None) -> None:
    with closing(sqlite3.connect(database_path or result.sqlite_path)) as connection:
        connection.execute(
            """
            INSERT INTO migration_runs (
                storage_dir,
                sqlite_path,
                started_at,
                finished_at,
                imported_count,
                skipped_count,
                native_imported_count,
                native_skipped_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.storage_dir,
                result.sqlite_path,
                result.started_at,
                result.finished_at,
                result.imported_count,
                result.skipped_count,
                result.native_imported_count,
                result.native_skipped_count,
            ),
        )
        connection.commit()
