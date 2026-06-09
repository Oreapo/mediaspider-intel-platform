from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.api.schemas.case import CaseCreateRequest
from app.domain.models.case import Case, CaseLink, CaseLinkType, CaseNote, CasePriority, CaseStatus
from app.infrastructure.persistence.sqlite_case_repository import SQLiteCaseRepository


def _case(case_id: str, updated_at: datetime) -> Case:
    return Case(
        id=case_id,
        case_name=f"Case {case_id}",
        case_type="lead_diversion",
        status=CaseStatus.OPEN,
        priority=CasePriority.HIGH,
        summary="case summary",
        owner="analyst",
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_sqlite_case_repository_crud_links_notes_and_cascade(tmp_path):
    repository = SQLiteCaseRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = _case("case_first", now)
    second = _case("case_second", now + timedelta(minutes=1))

    repository.save_case(first)
    repository.save_case(second)

    assert repository.get_case("case_first") == first
    assert [item.id for item in repository.list_cases()] == ["case_second", "case_first"]

    updated = first.model_copy(update={"status": CaseStatus.INVESTIGATING, "updated_at": now + timedelta(minutes=2)})
    repository.save_case(updated)
    assert repository.get_case("case_first").status == CaseStatus.INVESTIGATING

    link = CaseLink(
        id="clk_1",
        case_id="case_first",
        link_type=CaseLinkType.SIGNAL,
        target_id="sig_1",
        label="signal",
        source_ref_json={"reason": "test"},
        created_at=now,
        updated_at=now,
    )
    note = CaseNote(
        id="note_1",
        case_id="case_first",
        author="analyst",
        body="note body",
        note_type="investigation",
        created_at=now + timedelta(seconds=1),
        updated_at=now + timedelta(seconds=1),
    )
    repository.save_link(link)
    repository.save_note(note)

    assert repository.list_links("case_first") == [link]
    assert repository.list_notes("case_first") == [note]
    assert repository.delete_link("missing") is False
    assert repository.delete_note("missing") is False

    assert repository.delete_case("case_first") is True
    assert repository.get_case("case_first") is None
    assert repository.list_links("case_first") == []
    assert repository.list_notes("case_first") == []
    assert repository.delete_case("missing") is False


def test_app_container_can_switch_case_repository_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "cases.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_CASE_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    case = container.case_service.create_case(
        CaseCreateRequest(
            case_name="SQLite Case",
            case_type="lead_diversion",
            priority=CasePriority.HIGH,
            summary="sqlite case",
            owner="analyst",
        )
    )

    assert sqlite_path.exists()
    assert container.case_service.get_case(case.id).case_name == "SQLite Case"
