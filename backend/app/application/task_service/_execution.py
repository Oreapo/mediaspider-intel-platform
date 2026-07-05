from __future__ import annotations

from datetime import datetime

from ...domain.models.analysis import AnalysisScope
from ...domain.models.task import CollectionTask, TaskRun, TaskRunStatus


class TaskExecutionMixin:
    def diagnose_crawler(self, task_id: str) -> dict[str, object]:
        existing = self.repository.get_task(task_id)
        if existing is None:
            raise ValueError(f"Task {task_id} not found")
        if self.crawler_runner is None:
            return {
                "ready": False,
                "errors": ["Crawler runner is not configured"],
                "warnings": [],
                "command": [],
            }
        diagnose = getattr(self.crawler_runner, "diagnose", None)
        if not callable(diagnose):
            return {
                "ready": False,
                "errors": ["Crawler runner does not support diagnostics"],
                "warnings": [],
                "command": [],
            }
        return diagnose(self._apply_auth_profile(existing))

    def _execute_crawler_run(self, task: CollectionTask, run: TaskRun) -> TaskRun:
        if self.crawler_runner is None:
            return self._fail_run(run, "Crawler runner is not configured")
        if self.dataset_service is None:
            return self._fail_run(run, "Dataset service is not configured")

        try:
            result = self.crawler_runner.run(task, run)
            with self._run_state_lock:
                latest_run = self.repository.get_run(run.id)
                if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                    return latest_run
                run = self._save_run_progress(
                    latest_run or run,
                    "importing_results",
                    80,
                )

            dataset_ids: list[str] = []
            for output_file in result.output_files:
                dataset = self.dataset_service.create_dataset_from_file(
                    source_file=output_file,
                    dataset_name=self._dataset_name(task, output_file),
                    source_platform=task.platform,
                    source_task_id=task.id,
                    source_run_id=run.id,
                    scenario_type=task.scenario_type,
                    destination_prefix=f"crawler_runs/{run.id}",
                    tags=["crawler", self._item_type(output_file), task.task_mode.value],
                )
                dataset_ids.append(dataset.id)

            analysis_job_ids: list[str] = []
            analysis_failures: list[dict[str, str]] = []
            signal_ids: list[str] = []
            signal_failures: list[dict[str, str]] = []
            if result.return_code == 0 and dataset_ids:
                signal_extractors = self._signal_extractors(task)
                if signal_extractors and self.signal_extractor is not None:
                    with self._run_state_lock:
                        latest_run = self.repository.get_run(run.id)
                        if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                            return latest_run
                        run = self._save_run_progress(
                            latest_run or run,
                            "extracting_signals",
                            88,
                        )
                    signal_ids, signal_failures = self._extract_signals(
                        task,
                        run,
                        dataset_ids,
                        signal_extractors,
                    )

                analysis_types = self._analysis_types(task)
                if analysis_types and self.analysis_job_creator is not None:
                    with self._run_state_lock:
                        latest_run = self.repository.get_run(run.id)
                        if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                            return latest_run
                        run = self._save_run_progress(
                            latest_run or run,
                            "analyzing_results",
                            90,
                        )
                    analysis_job_ids, analysis_failures = self._create_analysis_jobs(
                        task,
                        dataset_ids,
                        analysis_types,
                    )

            finished_at = (result.finished_at or datetime.utcnow()).isoformat()
            status = TaskRunStatus.SUCCEEDED if result.return_code == 0 else TaskRunStatus.FAILED
            finished_progress_at = datetime.utcnow()
            updated = run.model_copy(
                update={
                    "status": status,
                    "finished_at": finished_at,
                    "log_path": str(result.log_path),
                    "result_dataset_id": dataset_ids[0] if dataset_ids else None,
                    "result_dataset_ids": dataset_ids,
                    "error_message": result.error_message,
                    "run_result_json": {
                        **run.run_result_json,
                        "return_code": result.return_code,
                        "command": result.redacted_command,
                        "output_files": [str(path) for path in result.output_files],
                        "dataset_ids": dataset_ids,
                        "signal_ids": signal_ids,
                        "signal_failures": signal_failures,
                        "analysis_job_ids": analysis_job_ids,
                        "analysis_failures": analysis_failures,
                        **(
                            {
                                "failure_diagnosis": self._failure_diagnosis(
                                    result.error_message,
                                    return_code=result.return_code,
                                )
                            }
                            if status == TaskRunStatus.FAILED
                            else {}
                        ),
                        "progress": self._progress_payload(
                            "completed" if status == TaskRunStatus.SUCCEEDED else "failed",
                            100,
                            finished_progress_at,
                        ),
                    },
                    "updated_at": finished_progress_at,
                }
            )
            with self._run_state_lock:
                latest_run = self.repository.get_run(run.id)
                if latest_run is not None and latest_run.status == TaskRunStatus.CANCELLED:
                    return latest_run
                return self.repository.save_run(updated)
        except Exception as exc:
            return self._fail_run(run, str(exc))

    def _analysis_profile_list(self, task: CollectionTask, key: str) -> list[str]:
        raw_value = task.analysis_profile_json.get(key, [])
        if isinstance(raw_value, str):
            raw_value = raw_value.split(",")
        if not isinstance(raw_value, list):
            return []
        return list(dict.fromkeys(str(item).strip() for item in raw_value if str(item).strip()))

    def _analysis_types(self, task: CollectionTask) -> list[str]:
        return self._analysis_profile_list(task, "analysis_types")

    def _signal_extractors(self, task: CollectionTask) -> list[str]:
        return self._analysis_profile_list(task, "signal_extractors")

    def _extract_signals(
        self,
        task: CollectionTask,
        run: TaskRun,
        dataset_ids: list[str],
        extractors: list[str],
    ) -> tuple[list[str], list[dict[str, str]]]:
        signal_ids: list[str] = []
        failures: list[dict[str, str]] = []
        raw_limit = task.analysis_profile_json.get("signal_limit", 100)
        try:
            limit = max(1, min(500, int(raw_limit)))
        except (TypeError, ValueError):
            limit = 100
        for dataset_id in dataset_ids:
            try:
                signals = self.signal_extractor(
                    dataset_id=dataset_id,
                    extractors=extractors,
                    limit=limit,
                    task_run_id=run.id,
                )
                signal_ids.extend(str(signal.id) for signal in signals)
            except Exception as exc:
                failures.append(
                    {
                        "dataset_id": dataset_id,
                        "error": str(exc),
                    }
                )
        return signal_ids, failures

    def _create_analysis_jobs(
        self,
        task: CollectionTask,
        dataset_ids: list[str],
        analysis_types: list[str],
    ) -> tuple[list[str], list[dict[str, str]]]:
        raw_scope = str(task.analysis_profile_json.get("analysis_scope", "platform"))
        try:
            analysis_scope = AnalysisScope(raw_scope)
        except ValueError:
            analysis_scope = AnalysisScope.PLATFORM

        job_ids: list[str] = []
        failures: list[dict[str, str]] = []
        for dataset_id in dataset_ids:
            for analysis_type in analysis_types:
                try:
                    job = self.analysis_job_creator(
                        dataset_id=dataset_id,
                        analysis_scope=analysis_scope,
                        analysis_type=analysis_type,
                        parameters_json={
                            "source_task_id": task.id,
                            "source_run_analysis": True,
                        },
                    )
                    job_ids.append(str(job.id))
                    if str(getattr(job.status, "value", job.status)) == "failed":
                        failures.append(
                            {
                                "dataset_id": dataset_id,
                                "analysis_type": analysis_type,
                                "error": str(job.error_message),
                            }
                        )
                except Exception as exc:
                    failures.append(
                        {
                            "dataset_id": dataset_id,
                            "analysis_type": analysis_type,
                            "error": str(exc),
                        }
                    )
        return job_ids, failures
