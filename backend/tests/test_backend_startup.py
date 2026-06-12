from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.models.dataset import Dataset, DatasetType
from app.domain.models.platform import PlatformKey
from app.infrastructure.persistence.sqlite_dataset_repository import SQLiteDatasetRepository
from scripts import start_backend
from scripts.start_backend import migrate_json_storage_if_needed


def test_startup_migrates_json_once_before_sqlite_repository_use(tmp_path, monkeypatch):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    sqlite_path = storage_dir / "platform.sqlite3"
    now = datetime.utcnow()
    dataset = Dataset(
        id="ds_startup",
        dataset_name="JSON dataset",
        dataset_type=DatasetType.RAW,
        source_platform=PlatformKey.XHS,
        created_at=now,
        updated_at=now,
    )
    dataset_file = storage_dir / "datasets.json"
    dataset_file.write_text(
        json.dumps([dataset.model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_AUTO_MIGRATE_JSON", "true")
    monkeypatch.setenv("MEDIASPIDER_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    result = migrate_json_storage_if_needed()

    assert result is not None
    assert result.sqlite_path == str(sqlite_path)
    assert result.native_imported_count == 1
    repository = SQLiteDatasetRepository(sqlite_path)
    assert repository.get_dataset(dataset.id) == dataset
    with sqlite3.connect(sqlite_path) as connection:
        recorded_path = connection.execute("SELECT sqlite_path FROM migration_runs").fetchone()[0]
    assert recorded_path == str(sqlite_path)

    changed_dataset = dataset.model_copy(update={"dataset_name": "Stale JSON update"})
    dataset_file.write_text(
        json.dumps([changed_dataset.model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )

    assert migrate_json_storage_if_needed() is None
    assert repository.get_dataset(dataset.id).dataset_name == "JSON dataset"


def test_startup_migration_does_not_leave_partial_target_database(tmp_path, monkeypatch):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    sqlite_path = storage_dir / "platform.sqlite3"
    temporary_path = storage_dir / "platform.sqlite3.migrating"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_AUTO_MIGRATE_JSON", "true")
    monkeypatch.setenv("MEDIASPIDER_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    class FailingMigrator:
        def __init__(self, _storage_dir, target_path):
            self.target_path = target_path

        def run(self):
            connection = sqlite3.connect(self.target_path)
            try:
                connection.execute("CREATE TABLE partial_record (id TEXT)")
                connection.commit()
            finally:
                connection.close()
            raise RuntimeError("simulated interrupted migration")

    monkeypatch.setattr(start_backend, "JsonToSQLiteMigrator", FailingMigrator)

    with pytest.raises(RuntimeError, match="interrupted migration"):
        migrate_json_storage_if_needed()

    assert not sqlite_path.exists()
    assert not temporary_path.exists()


def test_startup_migration_requires_explicit_enablement(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_AUTO_MIGRATE_JSON", "false")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    assert migrate_json_storage_if_needed() is None
    assert not sqlite_path.exists()
