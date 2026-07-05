from __future__ import annotations

from datetime import datetime

from ...domain.models.task import CollectionTask, TaskStatus


class TaskSchedulerMixin:
    def run_scheduled_tasks(
        self,
        *,
        now: datetime | None = None,
        execute_crawler: bool = True,
    ) -> dict[str, object]:
        current = now or datetime.utcnow()
        results: list[dict[str, object]] = []
        for task in self.repository.list_tasks():
            if task.status != TaskStatus.ENABLED:
                continue
            schedule_profile = self._schedule_profile(task)
            if not schedule_profile:
                continue
            cron_expr = str(schedule_profile.get("cron") or "").strip()
            if not cron_expr or not self._cron_matches(cron_expr, current):
                continue
            if not self._schedule_window_elapsed(task, current):
                continue
            active_run = self._active_run(task.id)
            if active_run is not None:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "skipped",
                        "reason": "active_run_exists",
                        "active_run_id": active_run.id,
                    }
                )
                continue
            max_retries = self._max_retries(task)
            retry_attempt = self._next_scheduled_retry_attempt(task.id, max_retries)
            if retry_attempt > max_retries:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "skipped",
                        "reason": "retry_exhausted",
                        "retry_attempt": retry_attempt - 1,
                        "max_retries": max_retries,
                    }
                )
                continue
            if not execute_crawler:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "ready",
                        "reason": "preflight",
                        "retry_attempt": retry_attempt,
                        "max_retries": max_retries,
                    }
                )
                continue
            try:
                run = self.start_run(
                    task.id,
                    trigger_type="cron",
                    execute_crawler=execute_crawler,
                    retry_attempt=retry_attempt,
                    max_retries=max_retries,
                )
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "started" if not execute_crawler else run.status.value,
                        "retry_attempt": retry_attempt,
                        "max_retries": max_retries,
                        "run": run.model_dump(mode="json"),
                    }
                )
            except ValueError as exc:
                results.append(
                    {
                        "task_id": task.id,
                        "task_name": task.task_name,
                        "status": "failed",
                        "error": str(exc),
                    }
                )
        return {"ran_at": current.isoformat(), "results": results}

    def _schedule_window_elapsed(self, task: CollectionTask, now: datetime) -> bool:
        if not task.last_run_at:
            return True
        try:
            last_run_at = datetime.fromisoformat(task.last_run_at)
        except ValueError:
            return True
        return last_run_at.replace(second=0, microsecond=0) < now.replace(second=0, microsecond=0)

    def _parse_cron(self, cron_expr: str) -> list[str]:
        fields = cron_expr.split()
        if len(fields) != 5:
            raise ValueError("cron_expr must contain five fields")
        return fields

    def _cron_matches(self, cron_expr: str, now: datetime) -> bool:
        try:
            minute, hour, day, month, weekday = self._parse_cron(cron_expr)
            return (
                self._field_matches(minute, now.minute, 0, 59)
                and self._field_matches(hour, now.hour, 0, 23)
                and self._field_matches(day, now.day, 1, 31)
                and self._field_matches(month, now.month, 1, 12)
                and self._field_matches(weekday, now.weekday(), 0, 6)
            )
        except ValueError:
            return False

    def _field_matches(self, field: str, value: int, minimum: int, maximum: int) -> bool:
        for part in field.split(","):
            if part == "*":
                return True
            if part.startswith("*/"):
                step = int(part[2:])
                if step <= 0:
                    raise ValueError("cron step must be positive")
                if value % step == 0:
                    return True
                continue
            if "-" in part:
                start, end = [int(item) for item in part.split("-", 1)]
                if start <= value <= end:
                    return True
                continue
            number = int(part)
            if number < minimum or number > maximum:
                raise ValueError("cron field value out of range")
            if value == number:
                return True
        return False
