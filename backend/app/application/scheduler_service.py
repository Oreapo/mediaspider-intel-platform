from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from .task_service import CollectionTaskService


logger = logging.getLogger(__name__)


class BackgroundScheduler:
    def __init__(
        self,
        task_service: CollectionTaskService,
        interval_seconds: int = 60,
        execute_crawler: bool = True,
    ) -> None:
        self.task_service = task_service
        self.interval_seconds = max(5, interval_seconds)
        self.execute_crawler = execute_crawler
        self.run_timeout_seconds = max(5, int(os.getenv("MEDIASPIDER_SCHEDULER_RUN_TIMEOUT_SECONDS", "300")))
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.last_result: dict[str, Any] | None = None
        self.last_error = ""
        self.run_history: list[dict[str, Any]] = []

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def run_once(self) -> dict[str, Any]:
        started_at = datetime.utcnow()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    self.task_service.run_scheduled_tasks,
                    now=started_at,
                    execute_crawler=self.execute_crawler,
                ),
                timeout=self.run_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            self.last_error = f"Scheduler run timed out after {self.run_timeout_seconds}s"
            self._record_history(
                {
                    "ran_at": started_at.isoformat(),
                    "status": "failed",
                    "error": self.last_error,
                    "results": [],
                }
            )
            raise TimeoutError(self.last_error) from exc
        self.last_result = result
        self.last_error = ""
        self._record_history({"status": "succeeded", **result})
        return result

    def _record_history(self, entry: dict[str, Any]) -> None:
        self.run_history = [entry, *self.run_history][:50]

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception as exc:  # pragma: no cover
                self.last_error = str(exc)
                logger.exception("Background scheduler run failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue
