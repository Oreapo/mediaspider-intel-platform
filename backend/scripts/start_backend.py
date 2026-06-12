from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import uvicorn


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.persistence.json_to_sqlite import (
    JsonToSQLiteMigrator,
    MigrationResult,
    persist_migration_run,
)


SQLITE_REPOSITORY_ENV_VARS = (
    "MEDIASPIDER_DATASET_REPOSITORY",
    "MEDIASPIDER_TASK_REPOSITORY",
    "MEDIASPIDER_ANALYSIS_REPOSITORY",
    "MEDIASPIDER_SIGNAL_REPOSITORY",
    "MEDIASPIDER_ENTITY_REPOSITORY",
    "MEDIASPIDER_CASE_REPOSITORY",
    "MEDIASPIDER_EVIDENCE_REPOSITORY",
    "MEDIASPIDER_REPORT_REPOSITORY",
    "MEDIASPIDER_NOTIFICATION_REPOSITORY",
    "MEDIASPIDER_PLATFORM_PROFILE_REPOSITORY",
    "MEDIASPIDER_AUDIT_REPOSITORY",
)
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def migrate_json_storage_if_needed() -> MigrationResult | None:
    auto_migrate = os.getenv("MEDIASPIDER_AUTO_MIGRATE_JSON", "false").strip().lower()
    repository_mode = os.getenv("MEDIASPIDER_REPOSITORY_MODE", "").strip().lower()
    sqlite_requested = repository_mode == "sqlite" or any(
        os.getenv(name, "").strip().lower() == "sqlite" for name in SQLITE_REPOSITORY_ENV_VARS
    )
    if auto_migrate not in TRUTHY_VALUES or not sqlite_requested:
        return None

    storage_dir = Path(os.getenv("MEDIASPIDER_STORAGE_DIR", str(BACKEND_ROOT / "storage")))
    sqlite_path = Path(
        os.getenv(
            "MEDIASPIDER_SQLITE_PATH",
            str(storage_dir / "mediaspider-intel.sqlite3"),
        )
    )
    if sqlite_path.exists():
        return None

    temporary_path = sqlite_path.with_name(f"{sqlite_path.name}.migrating")
    temporary_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path.unlink(missing_ok=True)
    try:
        result = JsonToSQLiteMigrator(storage_dir, temporary_path).run()
        result = replace(result, sqlite_path=str(sqlite_path))
        persist_migration_run(result, database_path=temporary_path)
        temporary_path.replace(sqlite_path)
    except Exception:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return result


def main() -> None:
    result = migrate_json_storage_if_needed()
    if result is not None:
        print(
            "JSON to SQLite startup migration completed: "
            f"staged={result.imported_count}, "
            f"native={result.native_imported_count}, "
            f"skipped={result.native_skipped_count}"
        )

    host = os.getenv("MEDIASPIDER_BACKEND_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.getenv("MEDIASPIDER_BACKEND_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
