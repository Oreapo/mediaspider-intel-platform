from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.models.dataset import Dataset, DatasetType
from app.domain.models.platform import PlatformKey
from app.domain.models.task import ScenarioType
from app.api.dependencies.container import AppContainer
from app.infrastructure.persistence.sqlite_dataset_repository import SQLiteDatasetRepository


def test_sqlite_dataset_repository_crud_and_ordering(tmp_path):
    repository = SQLiteDatasetRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = Dataset(
        id="ds_first",
        dataset_name="First",
        dataset_type=DatasetType.RAW,
        source_platform=PlatformKey.XHS,
        scenario_type=ScenarioType.LEAD_DIVERSION,
        storage_uri="first.jsonl",
        tags=["lead"],
        record_count=2,
        created_at=now,
        updated_at=now,
    )
    second = Dataset(
        id="ds_second",
        dataset_name="Second",
        dataset_type=DatasetType.NORMALIZED,
        source_platform=PlatformKey.DY,
        scenario_type=ScenarioType.TOPIC_WATCH,
        storage_uri="second.jsonl",
        tags=["topic", "video"],
        record_count=5,
        created_at=now + timedelta(minutes=1),
        updated_at=now + timedelta(minutes=1),
    )

    repository.save_dataset(first)
    repository.save_dataset(second)

    assert repository.get_dataset("ds_first") == first
    assert [item.id for item in repository.list_datasets()] == ["ds_second", "ds_first"]

    updated = first.model_copy(update={"dataset_name": "First Updated", "record_count": 3})
    repository.save_dataset(updated)

    assert repository.get_dataset("ds_first").dataset_name == "First Updated"
    assert repository.get_dataset("ds_first").record_count == 3
    assert repository.delete_dataset("ds_second") is True
    assert repository.delete_dataset("missing") is False
    assert [item.id for item in repository.list_datasets()] == ["ds_first"]


def test_app_container_can_switch_dataset_repository_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "datasets.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_DATASET_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    dataset = container.dataset_service.create_dataset(
        dataset_name="SQLite Dataset",
        source_platform=PlatformKey.XHS,
        dataset_type=DatasetType.RAW,
        scenario_type=ScenarioType.LEAD_DIVERSION,
        tags=["sqlite"],
    )

    assert sqlite_path.exists()
    assert container.dataset_service.get_dataset(dataset.id).dataset_name == "SQLite Dataset"


def test_sqlite_dataset_repository_filters_counts_and_paginates(tmp_path):
    repository = SQLiteDatasetRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    datasets = [
        Dataset(
            id="ds_xhs",
            dataset_name="XHS Lead Notes",
            dataset_type=DatasetType.RAW,
            source_platform=PlatformKey.XHS,
            scenario_type=ScenarioType.LEAD_DIVERSION,
            storage_uri="xhs_100%_leads.jsonl",
            tags=["lead", "spring"],
            created_at=now,
            updated_at=now,
        ),
        Dataset(
            id="ds_dy",
            dataset_name="DY Topic Videos",
            dataset_type=DatasetType.ANALYSIS_READY,
            source_platform=PlatformKey.DY,
            scenario_type=ScenarioType.TOPIC_WATCH,
            storage_uri="dy_topics.jsonl",
            tags=["topic", "video"],
            created_at=now + timedelta(minutes=1),
            updated_at=now + timedelta(minutes=1),
        ),
        Dataset(
            id="ds_xianyu",
            dataset_name="Xianyu Product Risk",
            dataset_type=DatasetType.NORMALIZED,
            source_platform=PlatformKey.XIANYU,
            scenario_type=ScenarioType.PRODUCT_RISK,
            storage_uri="xianyu_products.jsonl",
            tags=["seller", "price"],
            created_at=now + timedelta(minutes=2),
            updated_at=now + timedelta(minutes=2),
        ),
    ]
    for dataset in datasets:
        repository.save_dataset(dataset)

    assert [item.id for item in repository.list_datasets(source_platform=PlatformKey.XHS)] == ["ds_xhs"]
    assert [item.id for item in repository.list_datasets(tag="PRICE")] == ["ds_xianyu"]
    assert [item.id for item in repository.list_datasets(query="dy_topics")] == ["ds_dy"]
    assert [item.id for item in repository.list_datasets(query="100%")] == ["ds_xhs"]
    assert repository.count_datasets(scenario_type=ScenarioType.TOPIC_WATCH) == 1
    assert [item.id for item in repository.list_datasets(limit=1, offset=1)] == ["ds_dy"]
    assert repository.count_datasets() == 3
