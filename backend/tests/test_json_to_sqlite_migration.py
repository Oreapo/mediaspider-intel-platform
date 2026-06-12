from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.models.analysis import AnalysisJob, AnalysisJobStatus, AnalysisOutput, AnalysisScope
from app.domain.models.audit import AuditEvent
from app.domain.models.evidence import EvidencePacket
from app.domain.models.report import Report
from app.infrastructure.persistence.json_to_sqlite import JsonToSQLiteMigrator, persist_migration_run
from app.infrastructure.persistence.sqlite_analysis_repository import SQLiteAnalysisRepository
from app.infrastructure.persistence.sqlite_audit_repository import SQLiteAuditRepository
from app.infrastructure.persistence.sqlite_evidence_repository import SQLiteEvidenceRepository
from app.infrastructure.persistence.sqlite_report_repository import SQLiteReportRepository


def test_json_to_sqlite_migrates_known_collections(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    (storage_dir / "collection_tasks.json").write_text(
        json.dumps(
            [
                {
                    "id": "tsk_1",
                    "task_name": "XHS lead search",
                    "created_at": "2026-05-01T00:00:00",
                    "updated_at": "2026-05-01T00:10:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    (storage_dir / "datasets.json").write_text(
        json.dumps(
            [
                {
                    "id": "ds_1",
                    "dataset_name": "Crawler output",
                    "tags": ["crawler", "search"],
                    "created_at": "2026-05-01T00:11:00",
                    "updated_at": "2026-05-01T00:12:00",
                },
                {
                    "dataset_name": "No id dataset",
                    "created_at": "2026-05-01T00:13:00",
                    "updated_at": "2026-05-01T00:14:00",
                },
            ]
        ),
        encoding="utf-8",
    )

    sqlite_path = tmp_path / "storage.sqlite3"
    result = JsonToSQLiteMigrator(storage_dir, sqlite_path).run()
    persist_migration_run(result)

    assert result.imported_count == 3
    assert result.skipped_count == 0

    with sqlite3.connect(sqlite_path) as connection:
        records = connection.execute(
            "SELECT collection, record_id, payload_json FROM json_records ORDER BY collection, record_id"
        ).fetchall()
        assert len(records) == 3
        assert ("collection_tasks", "tsk_1") == records[0][:2]
        by_id = {record[1]: json.loads(record[2]) for record in records}
        assert by_id["ds_1"]["dataset_name"] == "Crawler output"
        assert by_id["datasets:1"]["dataset_name"] == "No id dataset"

        runs = connection.execute("SELECT imported_count, skipped_count FROM migration_runs").fetchall()
        assert runs == [(3, 0)]


def test_json_to_sqlite_handles_missing_and_invalid_files(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    (storage_dir / "signals.json").write_text("{broken", encoding="utf-8")

    sqlite_path = tmp_path / "storage.sqlite3"
    result = JsonToSQLiteMigrator(storage_dir, sqlite_path).run()

    assert result.imported_count == 0
    with sqlite3.connect(sqlite_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM json_records").fetchone()[0]
        assert count == 0


def test_json_to_sqlite_activates_native_repository_tables(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    now = datetime.utcnow()
    job = AnalysisJob(
        id="aj_migrated",
        dataset_id="ds_migrated",
        analysis_scope=AnalysisScope.COMMON,
        analysis_type="summary",
        status=AnalysisJobStatus.SUCCEEDED,
        parameters_json={"window": "30d"},
        created_at=now,
        updated_at=now,
    )
    output = AnalysisOutput(
        id="ao_migrated",
        analysis_job_id=job.id,
        output_type="summary",
        title="Migrated output",
        payload_json={"record_count": 12},
        created_at=now,
        updated_at=now,
    )
    packet = EvidencePacket(
        id="evp_migrated",
        case_id="case_migrated",
        packet_name="Migrated packet",
        storage_uri="evp_migrated.json",
        manifest_json={"schema_version": "evidence_packet.v1"},
        created_at=now,
        updated_at=now,
    )
    report = Report(
        id="rpt_migrated",
        case_id="case_migrated",
        report_name="Migrated report",
        storage_uri="rpt_migrated.md",
        content_markdown="# Migrated",
        created_at=now,
        updated_at=now,
    )
    audit_event = AuditEvent(
        id="aud_migrated",
        action="report.create",
        actor_username="analyst",
        actor_role="analyst",
        target_type="report",
        target_id=report.id,
        summary="Created migrated report",
        metadata_json={"source": "json-migration"},
        created_at=now,
        updated_at=now,
    )
    records = {
        "analysis_jobs.json": [job.model_dump(mode="json")],
        "analysis_outputs.json": [output.model_dump(mode="json")],
        "evidence_packets.json": [packet.model_dump(mode="json")],
        "reports.json": [report.model_dump(mode="json")],
        "audit_events.json": [audit_event.model_dump(mode="json")],
    }
    for file_name, payload in records.items():
        (storage_dir / file_name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    sqlite_path = tmp_path / "storage.sqlite3"
    result = JsonToSQLiteMigrator(storage_dir, sqlite_path).run()
    persist_migration_run(result)

    assert result.imported_count == 5
    assert result.native_imported_count == 5
    assert result.native_skipped_count == 0
    analysis_repository = SQLiteAnalysisRepository(sqlite_path)
    assert analysis_repository.get_job(job.id) == job
    assert analysis_repository.list_outputs(job.id) == [output]
    assert SQLiteEvidenceRepository(sqlite_path).get_packet(packet.id) == packet
    assert SQLiteReportRepository(sqlite_path).get_report(report.id) == report
    audit_repository = SQLiteAuditRepository(sqlite_path)
    assert audit_repository.list_events(target_id=report.id) == [audit_event]

    repeated_result = JsonToSQLiteMigrator(storage_dir, sqlite_path).run()
    assert repeated_result.native_imported_count == 5
    assert repeated_result.native_skipped_count == 0
    assert audit_repository.count_events(target_id=report.id) == 1

    with sqlite3.connect(sqlite_path) as connection:
        run = connection.execute(
            """
            SELECT imported_count, skipped_count, native_imported_count, native_skipped_count
            FROM migration_runs
            """
        ).fetchone()
    assert run == (5, 0, 5, 0)


def test_json_to_sqlite_staging_only_does_not_create_native_records(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    packet = EvidencePacket(
        id="evp_staging",
        case_id="case_staging",
        packet_name="Staging packet",
        storage_uri="staging.json",
    )
    (storage_dir / "evidence_packets.json").write_text(
        json.dumps([packet.model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )
    sqlite_path = tmp_path / "storage.sqlite3"

    result = JsonToSQLiteMigrator(storage_dir, sqlite_path, activate_native=False).run()

    assert result.imported_count == 1
    assert result.native_imported_count == 0
    with sqlite3.connect(sqlite_path) as connection:
        staged_count = connection.execute("SELECT COUNT(*) FROM json_records").fetchone()[0]
        native_table = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'evidence_packets'"
        ).fetchone()[0]
    assert staged_count == 1
    assert native_table == 0
