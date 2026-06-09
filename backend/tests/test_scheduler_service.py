from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.scheduler_service import BackgroundScheduler


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
