from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from .audit_service import AuditService
from .task_service import CollectionTaskService


logger = logging.getLogger(__name__)


class BackgroundScheduler:
    def __init__(
        self,
        task_service: CollectionTaskService,
        audit_service: AuditService | None = None,
        interval_seconds: int = 60,
        execute_crawler: bool = True,
    ) -> None:
        self.task_service = task_service
        self.audit_service = audit_service
        self.interval_seconds = max(5, interval_seconds)
        self.execute_crawler = execute_crawler
        self.run_timeout_seconds = max(5, int(os.getenv("MEDIASPIDER_SCHEDULER_RUN_TIMEOUT_SECONDS", "300")))
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._run_lock = asyncio.Lock()
        self._queued_runs = 0
        self.last_result: dict[str, Any] | None = None
        self.last_error = ""
        self.run_history = self._load_history()
        self._restore_last_status()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_executing(self) -> bool:
        return self._run_lock.locked()

    @property
    def queued_runs(self) -> int:
        return self._queued_runs

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

    async def run_once(
        self,
        *,
        now: datetime | None = None,
        execute_crawler: bool | None = None,
        trigger_type: str = "background",
    ) -> dict[str, Any]:
        was_queued = self._run_lock.locked()
        if was_queued:
            self._queued_runs += 1
        acquired = False
        release_deferred = False
        worker: asyncio.Task | None = None
        try:
            await self._run_lock.acquire()
            acquired = True
            if was_queued:
                self._queued_runs = max(0, self._queued_runs - 1)

            started_at = now or datetime.utcnow()
            should_execute_crawler = self.execute_crawler if execute_crawler is None else execute_crawler
            worker = asyncio.create_task(
                asyncio.to_thread(
                    self.task_service.run_scheduled_tasks,
                    now=started_at,
                    execute_crawler=should_execute_crawler,
                )
            )
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(worker),
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
                        "execute_crawler": should_execute_crawler,
                        "trigger_type": trigger_type,
                    }
                )
                self._defer_lock_release(worker)
                release_deferred = True
                raise TimeoutError(self.last_error) from exc
            except asyncio.CancelledError:
                if not worker.done():
                    self._defer_lock_release(worker)
                    release_deferred = True
                raise

            result = dict(result)
            result.setdefault("ran_at", started_at.isoformat())
            result.setdefault("results", [])
            self.last_result = result
            self.last_error = ""
            self._record_history(
                {
                    "status": "succeeded",
                    **result,
                    "execute_crawler": should_execute_crawler,
                    "trigger_type": trigger_type,
                }
            )
            return result
        finally:
            if was_queued and not acquired:
                self._queued_runs = max(0, self._queued_runs - 1)
            if acquired and not release_deferred:
                self._run_lock.release()

    def _defer_lock_release(self, worker: asyncio.Task) -> None:
        def release_after_worker(task: asyncio.Task) -> None:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Timed-out scheduler worker failed after the response returned")
            finally:
                if self._run_lock.locked():
                    self._run_lock.release()

        worker.add_done_callback(release_after_worker)

    def _record_history(self, entry: dict[str, Any]) -> None:
        self.run_history = [entry, *self.run_history][:50]
        if self.audit_service is not None:
            self.audit_service.record_system(
                action="scheduler.run",
                target_type="scheduler",
                target_id="collection_tasks",
                summary=f"Scheduler {entry.get('status', 'unknown')}: {len(entry.get('results', []))} results",
                metadata_json=entry,
            )

    def _load_history(self) -> list[dict[str, Any]]:
        if self.audit_service is None:
            return []
        events = self.audit_service.list_events(
            target_type="scheduler",
            target_id="collection_tasks",
            action="scheduler.run",
            limit=50,
        )
        history: list[dict[str, Any]] = []
        for event in events:
            entry = event.metadata_json
            if not isinstance(entry.get("results"), list) or not entry.get("ran_at"):
                continue
            history.append(dict(entry))
        return history

    def _restore_last_status(self) -> None:
        if not self.run_history:
            return
        latest = self.run_history[0]
        if latest.get("status") == "failed":
            self.last_error = str(latest.get("error") or "")
        for entry in self.run_history:
            if entry.get("status") == "succeeded":
                self.last_result = {
                    "ran_at": entry.get("ran_at"),
                    "results": entry.get("results", []),
                }
                break

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
