from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.dataset import Dataset


class DatasetRepository(ABC):
    @abstractmethod
    def list_datasets(self) -> list[Dataset]:
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
