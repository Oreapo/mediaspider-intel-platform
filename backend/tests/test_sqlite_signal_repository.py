from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.api.schemas.signal import SignalCreateRequest
from app.domain.models.dataset import DatasetType
from app.domain.models.platform import PlatformKey
from app.domain.models.signal import RiskLevel, Signal, SignalStatus, SignalType
from app.domain.models.task import ScenarioType
from app.infrastructure.persistence.sqlite_signal_repository import SQLiteSignalRepository


def _signal(signal_id: str, updated_at: datetime) -> Signal:
    return Signal(
        id=signal_id,
        dataset_id="ds_1",
        task_run_id="run_1",
        signal_type=SignalType.CONTACT_POINT_HIT,
        signal_source="test",
        risk_level=RiskLevel.HIGH,
        risk_score=88.5,
        summary=f"Signal {signal_id}",
        payload_json={"source_ref": {"dataset_id": "ds_1", "row_index": 0}},
        status=SignalStatus.NEW,
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_sqlite_signal_repository_crud_and_ordering(tmp_path):
    repository = SQLiteSignalRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = _signal("sig_first", now)
    second = _signal("sig_second", now + timedelta(minutes=1))

    repository.save_signal(first)
    repository.save_signal(second)

    assert repository.get_signal("sig_first") == first
    assert [item.id for item in repository.list_signals()] == ["sig_second", "sig_first"]

    updated = first.model_copy(
        update={
            "status": SignalStatus.CONFIRMED,
            "summary": "confirmed signal",
            "updated_at": now + timedelta(minutes=2),
        }
    )
    repository.save_signal(updated)

    assert repository.get_signal("sig_first").status == SignalStatus.CONFIRMED
    assert repository.get_signal("sig_first").summary == "confirmed signal"
    assert repository.delete_signal("sig_second") is True
    assert repository.delete_signal("missing") is False
    assert [item.id for item in repository.list_signals()] == ["sig_first"]


def test_app_container_can_switch_signal_repository_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "signals.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_SIGNAL_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    dataset = container.dataset_service.create_dataset(
        dataset_name="Signal Source Dataset",
        source_platform=PlatformKey.XHS,
        dataset_type=DatasetType.RAW,
        scenario_type=ScenarioType.LEAD_DIVERSION,
    )
    signal = container.signal_service.create_signal(
        SignalCreateRequest(
            dataset_id=dataset.id,
            signal_type=SignalType.MANUAL,
            signal_source="manual",
            risk_level=RiskLevel.MEDIUM,
            risk_score=61,
            summary="SQLite signal",
            payload_json={"source_ref": {"dataset_id": dataset.id}},
        )
    )

    assert sqlite_path.exists()
    assert container.signal_service.get_signal(signal.id).summary == "SQLite signal"


def test_sqlite_signal_repository_filters_counts_and_paginates(tmp_path):
    repository = SQLiteSignalRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    signals = [
        _signal("sig_contact", now).model_copy(
            update={
                "summary": "Contact point 100% match",
                "payload_json": {"source_ref": {"source_entity_id": "note_contact"}},
                "status": SignalStatus.CONFIRMED,
            }
        ),
        _signal("sig_risk", now + timedelta(minutes=1)).model_copy(
            update={
                "signal_type": SignalType.RISK_TERM_HIT,
                "risk_level": RiskLevel.MEDIUM,
                "summary": "Risk term hit",
                "payload_json": {"source_ref": {"source_entity_id": "note_risk"}},
            }
        ),
        _signal("sig_manual", now + timedelta(minutes=2)).model_copy(
            update={
                "dataset_id": "ds_2",
                "signal_type": SignalType.MANUAL,
                "risk_level": RiskLevel.LOW,
                "summary": "Manual review",
                "payload_json": {"source_ref": {"source_entity_id": "note_manual"}},
            }
        ),
    ]
    for signal in signals:
        repository.save_signal(signal)

    assert [item.id for item in repository.list_signals(dataset_id="ds_2")] == ["sig_manual"]
    assert [item.id for item in repository.list_signals(status=SignalStatus.CONFIRMED)] == ["sig_contact"]
    assert [item.id for item in repository.list_signals(query="note_risk")] == ["sig_risk"]
    assert [item.id for item in repository.list_signals(query="100%")] == ["sig_contact"]
    assert repository.count_signals(risk_level=RiskLevel.HIGH) == 1
    assert [item.id for item in repository.list_signals(limit=1, offset=1)] == ["sig_risk"]
    assert repository.count_signals() == 3
