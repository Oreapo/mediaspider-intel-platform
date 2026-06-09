from __future__ import annotations

import sys
import zipfile
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.backup_storage import create_backup


def test_create_backup_writes_zip_archive(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    (storage_dir / "datasets.json").write_text("[]", encoding="utf-8")

    archive = create_backup(storage_dir=storage_dir, output_dir=tmp_path / "backups", name="snapshot")

    assert archive.name == "snapshot.zip"
    assert archive.exists()
    with zipfile.ZipFile(archive) as zip_file:
      assert "datasets.json" in zip_file.namelist()
