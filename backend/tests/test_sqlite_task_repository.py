from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.models.platform import PlatformKey
from app.api.dependencies.container import AppContainer
from app.api.schemas.task import CollectionTaskCreateRequest
from app.domain.models.task import (
    CollectionTask,
    EntityType,
    ScenarioType,
    TaskMode,
    TaskRun,
    TaskRunStatus,
    TaskStatus,
)
from app.infrastructure.persistence.sqlite_task_repository import SQLiteCollectionTaskRepository


def _task(task_id: str, updated_at: datetime) -> CollectionTask:
    return CollectionTask(
        id=task_id,
        task_name=f"Task {task_id}",
        platform=PlatformKey.XHS,
        entity_type=EntityType.CONTENT,
        task_mode=TaskMode.SEARCH,
        scenario_type=ScenarioType.LEAD_DIVERSION,
        status=TaskStatus.ENABLED,
        task_payload_json={"keywords": ["导流"]},
        filter_payload_json={"start_page": 1},
        runtime_payload_json={"headless": True},
        storage_profile_json={"save_option": "jsonl"},
        analysis_profile_json={"analysis_types": ["summary"]},
        notes="sqlite task",
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_sqlite_task_repository_task_crud_and_runs(tmp_path):
    repository = SQLiteCollectionTaskRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = _task("tsk_first", now)
    second = _task("tsk_second", now + timedelta(minutes=1))

    repository.save_task(first)
    repository.save_task(second)

    assert repository.get_task("tsk_first") == first
    assert [item.id for item in repository.list_tasks()] == ["tsk_second", "tsk_first"]

    updated = first.model_copy(update={"notes": "updated", "last_run_at": now.isoformat()})
    repository.save_task(updated)
    assert repository.get_task("tsk_first").notes == "updated"
    assert repository.get_task("tsk_first").last_run_at == now.isoformat()

    first_run = TaskRun(
        id="run_first",
        task_id="tsk_first",
        status=TaskRunStatus.SUCCEEDED,
        started_at=now.isoformat(),
        finished_at=(now + timedelta(seconds=5)).isoformat(),
        result_dataset_ids=["ds_1"],
        run_result_json={"return_code": 0},
        created_at=now,
        updated_at=now,
    )
    second_run = TaskRun(
        id="run_second",
        task_id="tsk_second",
        status=TaskRunStatus.FAILED,
        error_message="boom",
        created_at=now + timedelta(minutes=1),
        updated_at=now + timedelta(minutes=1),
    )
    repository.save_run(first_run)
    repository.save_run(second_run)

    assert repository.get_run("run_first") == first_run
    assert [item.id for item in repository.list_runs()] == ["run_second", "run_first"]
    assert [item.id for item in repository.list_runs("tsk_first")] == ["run_first"]

    assert repository.delete_task("tsk_second") is True
    assert repository.delete_task("missing") is False
    assert [item.id for item in repository.list_tasks()] == ["tsk_first"]


def test_app_container_can_switch_task_repository_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "tasks.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_TASK_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    task = container.task_service.create_task(
        CollectionTaskCreateRequest(
            task_name="SQLite Task",
            platform=PlatformKey.XHS,
            entity_type=EntityType.CONTENT,
            task_mode=TaskMode.SEARCH,
            scenario_type=ScenarioType.LEAD_DIVERSION,
            status=TaskStatus.ENABLED,
            task_payload_json={"keywords": ["导流"]},
        )
    )

    assert sqlite_path.exists()
    assert container.task_service.get_task(task.id).task_name == "SQLite Task"


def test_sqlite_task_repository_filters_counts_and_paginates(tmp_path):
    repository = SQLiteCollectionTaskRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    tasks = [
        _task("tsk_xhs", now).model_copy(
            update={
                "task_name": "XHS Lead Search 100%",
                "task_payload_json": {"keywords": ["abc12345 导流"]},
                "notes": "contact lead watch",
            }
        ),
        _task("tsk_dy", now + timedelta(minutes=1)).model_copy(
            update={
                "task_name": "DY Topic Search",
                "platform": PlatformKey.DY,
                "scenario_type": ScenarioType.TOPIC_WATCH,
                "status": TaskStatus.DRAFT,
                "task_payload_json": {"keywords": ["topic propagation"]},
            }
        ),
        _task("tsk_xianyu", now + timedelta(minutes=2)).model_copy(
            update={
                "task_name": "Xianyu Seller Search",
                "platform": PlatformKey.XIANYU,
                "entity_type": EntityType.SELLER,
                "scenario_type": ScenarioType.SELLER_RISK,
                "status": TaskStatus.DISABLED,
                "task_payload_json": {"keywords": ["低价手机"]},
            }
        ),
    ]
    for task in tasks:
        repository.save_task(task)

    assert [item.id for item in repository.list_tasks(platform=PlatformKey.XHS)] == ["tsk_xhs"]
    assert [item.id for item in repository.list_tasks(status=TaskStatus.DISABLED)] == ["tsk_xianyu"]
    assert [item.id for item in repository.list_tasks(query="abc12345")] == ["tsk_xhs"]
    assert [item.id for item in repository.list_tasks(query="100%")] == ["tsk_xhs"]
    assert repository.count_tasks(scenario_type=ScenarioType.TOPIC_WATCH) == 1
    assert [item.id for item in repository.list_tasks(limit=1, offset=1)] == ["tsk_dy"]
    assert repository.count_tasks() == 3
