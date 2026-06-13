from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.dataset import Dataset, DatasetType
from ...domain.models.platform import PlatformKey
from ...domain.models.task import ScenarioType
from ...domain.repositories.dataset_repository import DatasetRepository


class JsonDatasetRepository(DatasetRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_datasets(
        self,
        *,
        source_platform: PlatformKey | None = None,
        dataset_type: DatasetType | None = None,
        scenario_type: ScenarioType | None = None,
        source_task_id: str = "",
        tag: str = "",
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Dataset]:
        datasets = self._filtered_datasets(
            source_platform=source_platform,
            dataset_type=dataset_type,
            scenario_type=scenario_type,
            source_task_id=source_task_id,
            tag=tag,
            query=query,
        )
        if offset > 0:
            datasets = datasets[offset:]
        if limit is not None:
            datasets = datasets[:limit]
        return datasets

    def count_datasets(
        self,
        *,
        source_platform: PlatformKey | None = None,
        dataset_type: DatasetType | None = None,
        scenario_type: ScenarioType | None = None,
        source_task_id: str = "",
        tag: str = "",
        query: str = "",
    ) -> int:
        return len(
            self._filtered_datasets(
                source_platform=source_platform,
                dataset_type=dataset_type,
                scenario_type=scenario_type,
                source_task_id=source_task_id,
                tag=tag,
                query=query,
            )
        )

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

    def _filtered_datasets(
        self,
        *,
        source_platform: PlatformKey | None,
        dataset_type: DatasetType | None,
        scenario_type: ScenarioType | None,
        source_task_id: str,
        tag: str,
        query: str,
    ) -> list[Dataset]:
        datasets = sorted(self._load_all(), key=lambda dataset: dataset.updated_at, reverse=True)
        if source_platform:
            datasets = [dataset for dataset in datasets if dataset.source_platform == source_platform]
        if dataset_type:
            datasets = [dataset for dataset in datasets if dataset.dataset_type == dataset_type]
        if scenario_type:
            datasets = [dataset for dataset in datasets if dataset.scenario_type == scenario_type]
        normalized_source_task_id = source_task_id.strip()
        if normalized_source_task_id:
            datasets = [
                dataset
                for dataset in datasets
                if dataset.source_task_id == normalized_source_task_id
            ]
        tag_needle = tag.strip().lower()
        if tag_needle:
            datasets = [
                dataset
                for dataset in datasets
                if any(tag_needle in item.lower() for item in dataset.tags)
            ]
        query_needle = query.strip().lower()
        if query_needle:
            datasets = [dataset for dataset in datasets if self._matches_query(dataset, query_needle)]
        return datasets

    def _matches_query(self, dataset: Dataset, needle: str) -> bool:
        values = [
            dataset.id,
            dataset.dataset_name,
            dataset.dataset_type.value,
            dataset.source_platform.value,
            dataset.scenario_type.value if dataset.scenario_type else "",
            dataset.storage_uri,
            dataset.schema_version,
            dataset.source_task_id or "",
            dataset.source_run_id or "",
            *dataset.tags,
        ]
        return any(needle in str(value).lower() for value in values)

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
