from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.dataset import Dataset, DatasetType
from ..models.platform import PlatformKey
from ..models.task import ScenarioType


class DatasetRepository(ABC):
    @abstractmethod
    def list_datasets(
        self,
        *,
        source_platform: PlatformKey | None = None,
        dataset_type: DatasetType | None = None,
        scenario_type: ScenarioType | None = None,
        tag: str = "",
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Dataset]:
        raise NotImplementedError

    @abstractmethod
    def count_datasets(
        self,
        *,
        source_platform: PlatformKey | None = None,
        dataset_type: DatasetType | None = None,
        scenario_type: ScenarioType | None = None,
        tag: str = "",
        query: str = "",
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_dataset(self, dataset_id: str) -> Dataset | None:
        raise NotImplementedError

    @abstractmethod
    def save_dataset(self, dataset: Dataset) -> Dataset:
        raise NotImplementedError

    @abstractmethod
    def delete_dataset(self, dataset_id: str) -> bool:
        raise NotImplementedError
