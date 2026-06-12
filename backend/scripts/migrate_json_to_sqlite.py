from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.persistence.json_to_sqlite import JsonToSQLiteMigrator, persist_migration_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate JSON storage into SQLite staging and native tables.")
    parser.add_argument(
        "--storage-dir",
        default=str(BACKEND_ROOT / "storage"),
        help="Directory containing JSON storage files.",
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(BACKEND_ROOT / "storage" / "mediaspider-intel.sqlite3"),
        help="SQLite database path to create or update.",
    )
    parser.add_argument(
        "--staging-only",
        action="store_true",
        help="Only preserve records in json_records without activating native repository tables.",
    )
    args = parser.parse_args()

    migrator = JsonToSQLiteMigrator(
        Path(args.storage_dir),
        Path(args.sqlite_path),
        activate_native=not args.staging_only,
    )
    result = migrator.run()
    persist_migration_run(result)
    print(
        json.dumps(
            {
                "sqlite_path": result.sqlite_path,
                "storage_dir": result.storage_dir,
                "imported_count": result.imported_count,
                "skipped_count": result.skipped_count,
                "native_imported_count": result.native_imported_count,
                "native_skipped_count": result.native_skipped_count,
                "collections": [item.__dict__ for item in result.collections],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
