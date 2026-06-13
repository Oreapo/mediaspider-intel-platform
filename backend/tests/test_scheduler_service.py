from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from threading import Event, Lock

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.scheduler_service import BackgroundScheduler
from app.application.audit_service import AuditService
from app.infrastructure.persistence.json_audit_repository import JsonAuditRepository
from app.infrastructure.persistence.sqlite_audit_repository import SQLiteAuditRepository


class FakeTaskService:
    def __init__(self) -> None:
        self.calls = []

    def run_scheduled_tasks(self, now=None, execute_crawler=True):
        self.calls.append({"now": now, "execute_crawler": execute_crawler})
        return {"results": [], "execute_crawler": execute_crawler}


@pytest.mark.anyio
async def test_scheduler_run_once_records_result():
    task_service = FakeTaskService()
    scheduler = BackgroundScheduler(task_service, interval_seconds=5, execute_crawler=False)

    result = await scheduler.run_once()

    assert result["execute_crawler"] is False
    assert scheduler.last_result == result
    assert scheduler.run_history[0]["status"] == "succeeded"
    assert scheduler.run_history[0]["results"] == []
    assert task_service.calls[0]["execute_crawler"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("repository_kind", ["json", "sqlite"])
async def test_scheduler_history_persists_and_restores(tmp_path, repository_kind):
    repository = (
        JsonAuditRepository(tmp_path / "audit.json")
        if repository_kind == "json"
        else SQLiteAuditRepository(tmp_path / "audit.sqlite3")
    )
    audit_service = AuditService(repository)
    scheduler = BackgroundScheduler(
        FakeTaskService(),
        audit_service,
        interval_seconds=5,
        execute_crawler=False,
    )

    await scheduler.run_once(trigger_type="manual")

    restored = BackgroundScheduler(
        FakeTaskService(),
        audit_service,
        interval_seconds=5,
        execute_crawler=False,
    )
    assert restored.run_history[0]["status"] == "succeeded"
    assert restored.run_history[0]["trigger_type"] == "manual"
    assert restored.last_result == {
        "ran_at": restored.run_history[0]["ran_at"],
        "results": [],
    }


class SlowTaskService(FakeTaskService):
    def run_scheduled_tasks(self, now=None, execute_crawler=True):
        time.sleep(0.05)
        return super().run_scheduled_tasks(now=now, execute_crawler=execute_crawler)


@pytest.mark.anyio
async def test_scheduler_timeout_is_persisted_and_restored(tmp_path):
    audit_service = AuditService(JsonAuditRepository(tmp_path / "audit.json"))
    scheduler = BackgroundScheduler(SlowTaskService(), audit_service, interval_seconds=5)
    scheduler.run_timeout_seconds = 0.01

    with pytest.raises(TimeoutError, match="timed out"):
        await scheduler.run_once()

    assert scheduler.is_executing is True
    for _ in range(100):
        if not scheduler.is_executing:
            break
        await asyncio.sleep(0.01)
    assert scheduler.is_executing is False
    restored = BackgroundScheduler(FakeTaskService(), audit_service, interval_seconds=5)
    assert restored.run_history[0]["status"] == "failed"
    assert restored.last_error == scheduler.last_error


class BlockingTaskService(FakeTaskService):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()
        self.guard = Lock()
        self.active_runs = 0
        self.max_active_runs = 0

    def run_scheduled_tasks(self, now=None, execute_crawler=True):
        with self.guard:
            self.active_runs += 1
            self.max_active_runs = max(self.max_active_runs, self.active_runs)
        self.started.set()
        try:
            self.release.wait(timeout=1)
            return super().run_scheduled_tasks(now=now, execute_crawler=execute_crawler)
        finally:
            with self.guard:
                self.active_runs -= 1


@pytest.mark.anyio
async def test_scheduler_serializes_overlapping_runs_and_reports_queue():
    task_service = BlockingTaskService()
    scheduler = BackgroundScheduler(task_service, interval_seconds=5)

    first_run = asyncio.create_task(scheduler.run_once(trigger_type="background"))
    assert await asyncio.to_thread(task_service.started.wait, 1)
    second_run = asyncio.create_task(scheduler.run_once(trigger_type="manual"))
    for _ in range(20):
        if scheduler.queued_runs == 1:
            break
        await asyncio.sleep(0.01)

    assert scheduler.is_executing is True
    assert scheduler.queued_runs == 1
    task_service.release.set()
    await asyncio.gather(first_run, second_run)

    assert task_service.max_active_runs == 1
    assert scheduler.is_executing is False
    assert scheduler.queued_runs == 0
