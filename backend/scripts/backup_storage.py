from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def create_backup(storage_dir: Path, output_dir: Path, name: str | None = None) -> Path:
    storage_dir = storage_dir.resolve()
    output_dir = output_dir.resolve()
    if not storage_dir.exists():
        raise FileNotFoundError(f"Storage directory not found: {storage_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_name = name or f"mediaspider-storage-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    archive_base = output_dir / backup_name
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=storage_dir)
    return Path(archive_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a zip backup of MediaSpider storage.")
    parser.add_argument("--storage-dir", default="backend/storage", help="Storage directory to back up.")
    parser.add_argument("--output-dir", default="backups", help="Directory where the zip archive is written.")
    parser.add_argument("--name", default="", help="Optional archive name without extension.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive = create_backup(
        storage_dir=Path(args.storage_dir),
        output_dir=Path(args.output_dir),
        name=args.name or None,
    )
    print(archive)


if __name__ == "__main__":
    main()
