from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.domain.models.evidence import EvidencePacket
from app.domain.models.report import Report, ReportStatus, ReportType
from app.infrastructure.persistence.sqlite_evidence_repository import SQLiteEvidenceRepository
from app.infrastructure.persistence.sqlite_report_repository import SQLiteReportRepository


def test_sqlite_evidence_repository_crud_and_ordering(tmp_path):
    repository = SQLiteEvidenceRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = EvidencePacket(
        id="evp_first",
        case_id="case_1",
        packet_name="First Packet",
        storage_uri="first.json",
        manifest_json={"summary": {"signal_count": 1}},
        created_at=now,
        updated_at=now,
    )
    second = EvidencePacket(
        id="evp_second",
        case_id="case_1",
        packet_name="Second Packet",
        storage_uri="second.json",
        manifest_json={"summary": {"signal_count": 2}},
        created_at=now + timedelta(minutes=1),
        updated_at=now + timedelta(minutes=1),
    )

    repository.save_packet(first)
    repository.save_packet(second)

    assert repository.get_packet("evp_first") == first
    assert [item.id for item in repository.list_packets()] == ["evp_second", "evp_first"]

    updated = first.model_copy(update={"packet_name": "Updated Packet", "updated_at": now + timedelta(minutes=2)})
    repository.save_packet(updated)
    assert repository.get_packet("evp_first").packet_name == "Updated Packet"
    assert repository.delete_packet("evp_second") is True
    assert repository.delete_packet("missing") is False


def test_sqlite_report_repository_crud_and_ordering(tmp_path):
    repository = SQLiteReportRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = Report(
        id="rpt_first",
        case_id="case_1",
        report_name="First Report",
        report_type=ReportType.INVESTIGATION_BRIEF,
        status=ReportStatus.GENERATED,
        storage_uri="first.md",
        content_markdown="# First",
        summary_json={"signal_count": 1},
        created_at=now,
        updated_at=now,
    )
    second = Report(
        id="rpt_second",
        case_id="case_1",
        report_name="Second Report",
        report_type=ReportType.CASE_SUMMARY,
        status=ReportStatus.DRAFT,
        storage_uri="second.md",
        content_markdown="# Second",
        summary_json={"signal_count": 2},
        created_at=now + timedelta(minutes=1),
        updated_at=now + timedelta(minutes=1),
    )

    repository.save_report(first)
    repository.save_report(second)

    assert repository.get_report("rpt_first") == first
    assert [item.id for item in repository.list_reports()] == ["rpt_second", "rpt_first"]

    updated = first.model_copy(update={"status": ReportStatus.ARCHIVED, "updated_at": now + timedelta(minutes=2)})
    repository.save_report(updated)
    assert repository.get_report("rpt_first").status == ReportStatus.ARCHIVED
    assert repository.delete_report("rpt_second") is True
    assert repository.delete_report("missing") is False


def test_app_container_can_switch_evidence_and_report_repositories_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "artifacts.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_EVIDENCE_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_REPORT_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    packet = container.evidence_service.repository.save_packet(
        EvidencePacket(
            case_id="case_1",
            packet_name="SQLite Packet",
            storage_uri="packet.json",
            manifest_json={"ok": True},
        )
    )
    report = container.report_service.repository.save_report(
        Report(
            case_id="case_1",
            report_name="SQLite Report",
            storage_uri="report.md",
            content_markdown="# Report",
        )
    )

    assert sqlite_path.exists()
    assert container.evidence_service.get_packet(packet.id).packet_name == "SQLite Packet"
    assert container.report_service.get_report(report.id).report_name == "SQLite Report"
