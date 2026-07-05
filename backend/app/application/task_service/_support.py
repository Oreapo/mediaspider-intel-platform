from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.task import CollectionTask, TaskRun, TaskRunStatus


TASK_QUEUE_PRIORITY_WEIGHTS = {
    "low": 0,
    "normal": 10,
    "high": 20,
    "critical": 30,
}


class TaskRunSupportMixin:
    """Cross-cutting helpers shared by the queue, retry, scheduler, and execution mixins."""

    def _fail_run(self, run: TaskRun, error_message: str) -> TaskRun:
        failed_at = datetime.utcnow()
        updated = run.model_copy(
            update={
                "status": TaskRunStatus.FAILED,
                "finished_at": failed_at.isoformat(),
                "error_message": error_message,
                "run_result_json": {
                    **run.run_result_json,
                    "failure_diagnosis": self._failure_diagnosis(error_message),
                    "progress": self._progress_payload("failed", 100, failed_at),
                },
                "updated_at": failed_at,
            }
        )
        with self._run_state_lock:
            latest_run = self.repository.get_run(run.id)
            if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                return latest_run
            return self.repository.save_run(updated)

    def _save_run_progress(
        self,
        run: TaskRun,
        stage: str,
        percent: int,
    ) -> TaskRun:
        updated_at = datetime.utcnow()
        updated = run.model_copy(
            update={
                "run_result_json": {
                    **run.run_result_json,
                    "progress": self._progress_payload(stage, percent, updated_at),
                },
                "updated_at": updated_at,
            }
        )
        return self.repository.save_run(updated)

    def _progress_payload(
        self,
        stage: str,
        percent: int,
        updated_at: datetime,
    ) -> dict[str, object]:
        return {
            "stage": stage,
            "percent": max(0, min(100, int(percent))),
            "updated_at": updated_at.isoformat(),
        }

    def _dataset_name(self, task: CollectionTask, output_file: Path) -> str:
        return f"{task.task_name} / {self._item_type(output_file)} / {output_file.stem}"

    def _item_type(self, output_file: Path) -> str:
        parts = output_file.stem.split("_")
        if len(parts) >= 2:
            return parts[-2]
        return "records"

    def _apply_auth_profile(self, task: CollectionTask) -> CollectionTask:
        if not task.auth_profile_id or self.auth_profile_resolver is None:
            return task
        auth_payload = self.auth_profile_resolver(task.auth_profile_id)
        runtime_payload = {**task.runtime_payload_json, **auth_payload}
        return task.model_copy(update={"runtime_payload_json": runtime_payload})

    def _schedule_profile(self, task: CollectionTask) -> dict[str, object]:
        profile = task.runtime_payload_json.get("schedule_profile")
        return profile if isinstance(profile, dict) else {}

    def _active_run(self, task_id: str) -> TaskRun | None:
        for run in self.repository.list_runs(task_id):
            if run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                if (
                    self.repository.supports_run_leases
                    and not self.repository.is_run_lease_active(task_id, run.id)
                ):
                    recovered_at = datetime.utcnow()
                    was_pending = run.status == TaskRunStatus.PENDING
                    self.repository.save_run(
                        run.model_copy(
                            update={
                                "status": (
                                    TaskRunStatus.CANCELLED
                                    if was_pending
                                    else TaskRunStatus.FAILED
                                ),
                                "finished_at": recovered_at.isoformat(),
                                "error_message": (
                                    "Queued task run lease expired"
                                    if was_pending
                                    else "Running task lease expired"
                                ),
                                "run_result_json": {
                                    **run.run_result_json,
                                    "recovered_after_lease_expiry": True,
                                    "previous_status": run.status.value,
                                    **(
                                        {
                                            "failure_diagnosis": self._failure_diagnosis(
                                                "Running task lease expired",
                                            )
                                        }
                                        if not was_pending
                                        else {}
                                    ),
                                    "progress": self._progress_payload(
                                        "cancelled" if was_pending else "failed",
                                        100,
                                        recovered_at,
                                    ),
                                },
                                "updated_at": recovered_at,
                            }
                        )
                    )
                    continue
                return run
        return None

    def _failure_diagnosis(
        self,
        error_message: str,
        *,
        return_code: int | None = None,
    ) -> dict[str, object]:
        normalized = error_message.strip().lower()

        if return_code == 124 or "timed out" in normalized or "timeout" in normalized:
            code = "timeout"
            retryable = True
            suggestions = ["increase_timeout", "reduce_scope", "check_network"]
        elif "mediacrawler root is not configured" in normalized:
            code = "configuration"
            retryable = False
            suggestions = ["diagnose_crawler", "check_crawler_config"]
        elif any(
            marker in normalized
            for marker in (
                "cookie",
                "login",
                "auth",
                "credential",
                "unauthorized",
                "forbidden",
                "扫码",
                "登录",
            )
        ):
            code = "authentication"
            retryable = False
            suggestions = ["refresh_auth_profile", "diagnose_crawler"]
        elif any(
            marker in normalized
            for marker in (
                "root not found",
                "entrypoint",
                "not configured",
                "does not support",
                "requires task_payload_json",
                "requires runtime_payload_json",
                "save_option must",
                "has no mediacrawler",
            )
        ):
            code = "configuration"
            retryable = False
            suggestions = ["diagnose_crawler", "check_crawler_config"]
        elif any(
            marker in normalized
            for marker in (
                "connection",
                "network",
                "dns",
                "proxy",
                "ssl",
                "http 429",
                "too many requests",
                "连接",
                "网络",
                "代理",
            )
        ):
            code = "network"
            retryable = True
            suggestions = ["check_network", "check_proxy", "retry_run"]
        elif any(
            marker in normalized
            for marker in (
                "permission denied",
                "no space left",
                "read-only",
                "storage",
                "dataset",
                "json decode",
                "csv",
                "入库",
                "存储",
            )
        ):
            code = "storage"
            retryable = False
            suggestions = ["check_storage", "inspect_log"]
        elif "backend restart" in normalized or "lease expired" in normalized:
            code = "interrupted"
            retryable = True
            suggestions = ["retry_run", "check_backend_stability"]
        elif return_code is not None:
            code = "crawler_exit"
            retryable = True
            suggestions = ["inspect_log", "diagnose_crawler", "retry_run"]
        else:
            code = "unexpected_error"
            retryable = False
            suggestions = ["inspect_log", "diagnose_crawler"]

        return {
            "code": code,
            "retryable": retryable,
            "suggestions": suggestions,
            "return_code": return_code,
        }
