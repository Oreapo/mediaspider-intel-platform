from __future__ import annotations

from ...domain.models.task import CollectionTask, TaskRun, TaskRunStatus


class TaskRetryMixin:
    def retry_run(self, task_id: str, run_id: str) -> TaskRun:
        source_run = self.repository.get_run(run_id)
        if source_run is None or source_run.task_id != task_id:
            raise ValueError("Task run not found")
        if source_run.status != TaskRunStatus.FAILED:
            raise ValueError(
                f"Only failed task runs can be retried; current status is {source_run.status.value}"
            )

        diagnosis = source_run.run_result_json.get("failure_diagnosis")
        if not isinstance(diagnosis, dict):
            diagnosis = self._failure_diagnosis(
                source_run.error_message,
                return_code=self._optional_int(
                    source_run.run_result_json.get("return_code")
                ),
            )
        if diagnosis.get("retryable") is not True:
            raise ValueError("Task run diagnosis requires fixing the failure before retry")

        max_retries = self._non_negative_int(
            source_run.run_result_json.get("max_retries"),
            0,
        )
        retry_root_run_id = str(
            source_run.run_result_json.get("retry_root_run_id") or source_run.id
        )
        retry_attempt = self._next_lineage_retry_attempt(task_id, retry_root_run_id)
        return self.submit_run(
            task_id,
            trigger_type="manual_retry",
            execute_crawler=True,
            retry_attempt=retry_attempt,
            max_retries=max_retries,
            retry_of_run_id=source_run.id,
            retry_root_run_id=retry_root_run_id,
        )

    def _next_lineage_retry_attempt(self, task_id: str, retry_root_run_id: str) -> int:
        attempts = [
            self._non_negative_int(run.run_result_json.get("retry_attempt"), 0)
            for run in self.repository.list_runs(task_id)
            if run.id == retry_root_run_id
            or run.run_result_json.get("retry_root_run_id") == retry_root_run_id
        ]
        return max(attempts, default=0) + 1

    def _non_negative_int(self, value: object, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def _optional_int(self, value: object) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _max_retries(self, task: CollectionTask) -> int:
        schedule_profile = self._schedule_profile(task)
        raw_value = schedule_profile.get("max_retries", task.runtime_payload_json.get("max_retries", 0))
        try:
            return max(0, int(raw_value))
        except (TypeError, ValueError):
            return 0

    def _next_scheduled_retry_attempt(self, task_id: str, max_retries: int) -> int:
        failed_attempts = 0
        for run in self.repository.list_runs(task_id):
            if run.trigger_type != "cron":
                continue
            if run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
                return max_retries + 1
            if run.status == TaskRunStatus.SUCCEEDED:
                return 0
            if run.status == TaskRunStatus.FAILED:
                failed_attempts += 1
                continue
            return 0
        return failed_attempts
