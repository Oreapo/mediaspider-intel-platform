from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.dataset import Dataset
from ...domain.repositories.dataset_repository import DatasetRepository


class JsonDatasetRepository(DatasetRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_datasets(self) -> list[Dataset]:
        return sorted(self._load_all(), key=lambda dataset: dataset.updated_at, reverse=True)

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        for dataset in self._load_all():
            if dataset.id == dataset_id:
                return dataset
        return None

    def save_dataset(self, dataset: Dataset) -> Dataset:
        datasets = self._load_all()
        replaced = False
        for index, existing in enumerate(datasets):
            if existing.id == dataset.id:
                datasets[index] = dataset
                replaced = True
                break
        if not replaced:
            datasets.append(dataset)
        self._save_all(datasets)
        return dataset

    def delete_dataset(self, dataset_id: str) -> bool:
        datasets = self._load_all()
        filtered = [dataset for dataset in datasets if dataset.id != dataset_id]
        if len(filtered) == len(datasets):
            return False
        self._save_all(filtered)
        return True

    def _load_all(self) -> list[Dataset]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        datasets: list[Dataset] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                datasets.append(Dataset.model_validate(item))
            except Exception:
                continue
        return datasets

    def _save_all(self, datasets: list[Dataset]):
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([dataset.model_dump(mode="json") for dataset in datasets], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
