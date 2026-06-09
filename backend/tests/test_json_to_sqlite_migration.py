from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.persistence.json_to_sqlite import JsonToSQLiteMigrator, persist_migration_run


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
