from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.models.dataset import Dataset, DatasetType
from ..domain.models.platform import PlatformKey
from ..domain.models.task import ScenarioType
from ..domain.repositories.dataset_repository import DatasetRepository


class DatasetService:
    SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".csv"}

    def __init__(self, repository: DatasetRepository, storage_root: Path):
        self.repository = repository
        self.storage_root = storage_root
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def list_datasets(self) -> list[Dataset]:
        return self.repository.list_datasets()

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        return self.repository.get_dataset(dataset_id)

    def create_dataset(
        self,
        *,
        dataset_name: str,
        source_platform: PlatformKey,
        dataset_type: DatasetType = DatasetType.RAW,
        source_task_id: str | None = None,
        source_run_id: str | None = None,
        scenario_type: ScenarioType | None = None,
        storage_uri: str = "",
        tags: list[str] | None = None,
    ) -> Dataset:
        dataset = Dataset(
            dataset_name=dataset_name,
            dataset_type=dataset_type,
            source_platform=source_platform,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
            scenario_type=scenario_type,
            storage_uri=storage_uri,
            tags=tags or [],
            snapshot_time=datetime.utcnow().isoformat(),
        )
        dataset.record_count = self._count_records(storage_uri) if storage_uri else 0
        return self.repository.save_dataset(dataset)

    def create_dataset_from_file(
        self,
        *,
        source_file: Path,
        dataset_name: str,
        source_platform: PlatformKey,
        dataset_type: DatasetType = DatasetType.RAW,
        source_task_id: str | None = None,
        source_run_id: str | None = None,
        scenario_type: ScenarioType | None = None,
        destination_prefix: str = "imports",
        tags: list[str] | None = None,
    ) -> Dataset:
        if source_file.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported dataset storage format: {source_file.suffix}")
        destination_dir = self._resolve_storage_path(destination_prefix)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination_file = self._unique_path(destination_dir / source_file.name)
        shutil.copy2(source_file, destination_file)
        storage_uri = destination_file.relative_to(self.storage_root).as_posix()
        return self.create_dataset(
            dataset_name=dataset_name,
            dataset_type=dataset_type,
            source_platform=source_platform,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
            scenario_type=scenario_type,
            storage_uri=storage_uri,
            tags=tags,
        )

    def delete_dataset(self, dataset_id: str, delete_storage: bool = False) -> bool:
        dataset = self.repository.get_dataset(dataset_id)
        if dataset is None:
            return False
        deleted = self.repository.delete_dataset(dataset_id)
        if deleted and delete_storage and dataset.storage_uri:
            file_path = self._resolve_storage_path(dataset.storage_uri)
            if file_path.exists():
                file_path.unlink()
        return deleted

    def preview_dataset(self, dataset_id: str, limit: int = 50) -> dict[str, Any]:
        dataset = self.repository.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        if not dataset.storage_uri:
            return {"columns": [], "rows": [], "mode": "table", "total": 0}
        file_path = self._resolve_storage_path(dataset.storage_uri)
        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported dataset storage format: {suffix}")
        rows = self._load_rows(file_path, limit)
        columns = self._extract_columns(rows)
        normalized_rows = [[self._stringify(row.get(column, "")) for column in columns] for row in rows]
        return {"columns": columns, "rows": normalized_rows, "mode": "table", "total": len(rows)}

    def _resolve_storage_path(self, storage_uri: str) -> Path:
        file_path = (self.storage_root / storage_uri).resolve()
        file_path.relative_to(self.storage_root.resolve())
        return file_path

    def _count_records(self, storage_uri: str) -> int:
        file_path = self._resolve_storage_path(storage_uri)
        if not file_path.exists():
            return 0
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return len(data)
            return 1
        if suffix == ".jsonl":
            return sum(1 for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip())
        if suffix == ".csv":
            with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
                return max(sum(1 for _ in handle) - 1, 0)
        return 0

    def _load_rows(self, file_path: Path, limit: int) -> list[dict[str, Any]]:
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[:limit]
            return [data]
        if suffix == ".jsonl":
            rows: list[dict[str, Any]] = []
            with file_path.open("r", encoding="utf-8") as handle:
                for index, line in enumerate(handle):
                    if index >= limit:
                        break
                    text = line.strip()
                    if text:
                        rows.append(json.loads(text))
            return rows
        if suffix == ".csv":
            with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = []
                for index, row in enumerate(reader):
                    if index >= limit:
                        break
                    rows.append(row)
            return rows
        return []

    def _extract_columns(self, rows: list[dict[str, Any]]) -> list[str]:
        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(str(key))
        return columns

    def _unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        for index in range(1, 1000):
            candidate = path.with_name(f"{stem}_{index}{suffix}")
            if not candidate.exists():
                return candidate
        raise ValueError(f"Cannot create unique dataset file path for {path.name}")

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
