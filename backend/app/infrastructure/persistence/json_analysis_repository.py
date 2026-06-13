from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.analysis import AnalysisJob, AnalysisOutput
from ...domain.repositories.analysis_repository import AnalysisRepository


class JsonAnalysisRepository(AnalysisRepository):
    def __init__(self, jobs_file: Path, outputs_file: Path):
        self.jobs_file = jobs_file
        self.outputs_file = outputs_file

    def list_jobs(
        self,
        *,
        dataset_id: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[AnalysisJob]:
        jobs = self._filtered_jobs(dataset_id=dataset_id)
        if offset > 0:
            jobs = jobs[offset:]
        if limit is not None:
            jobs = jobs[:limit]
        return jobs

    def count_jobs(self, *, dataset_id: str = "") -> int:
        return len(self._filtered_jobs(dataset_id=dataset_id))

    def get_job(self, job_id: str) -> AnalysisJob | None:
        for job in self._load_jobs():
            if job.id == job_id:
                return job
        return None

    def save_job(self, job: AnalysisJob) -> AnalysisJob:
        jobs = self._load_jobs()
        replaced = False
        for index, existing in enumerate(jobs):
            if existing.id == job.id:
                jobs[index] = job
                replaced = True
                break
        if not replaced:
            jobs.append(job)
        self._save_jobs(jobs)
        return job

    def list_outputs(self, job_id: str) -> list[AnalysisOutput]:
        return self.list_outputs_for_jobs([job_id])

    def list_outputs_for_jobs(self, job_ids: list[str]) -> list[AnalysisOutput]:
        normalized_job_ids = {job_id.strip() for job_id in job_ids if job_id.strip()}
        if not normalized_job_ids:
            return []
        return sorted(
            [
                output
                for output in self._load_outputs()
                if output.analysis_job_id in normalized_job_ids
            ],
            key=lambda output: output.updated_at,
            reverse=True,
        )

    def save_output(self, output: AnalysisOutput) -> AnalysisOutput:
        outputs = self._load_outputs()
        replaced = False
        for index, existing in enumerate(outputs):
            if existing.id == output.id:
                outputs[index] = output
                replaced = True
                break
        if not replaced:
            outputs.append(output)
        self._save_outputs(outputs)
        return output

    def _load_jobs(self) -> list[AnalysisJob]:
        if not self.jobs_file.exists():
            return []
        try:
            raw = json.loads(self.jobs_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        jobs: list[AnalysisJob] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                jobs.append(AnalysisJob.model_validate(item))
            except Exception:
                continue
        return jobs

    def _filtered_jobs(self, *, dataset_id: str) -> list[AnalysisJob]:
        jobs = sorted(self._load_jobs(), key=lambda job: job.updated_at, reverse=True)
        normalized_dataset_id = dataset_id.strip()
        if normalized_dataset_id:
            jobs = [job for job in jobs if job.dataset_id == normalized_dataset_id]
        return jobs

    def _load_outputs(self) -> list[AnalysisOutput]:
        if not self.outputs_file.exists():
            return []
        try:
            raw = json.loads(self.outputs_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        outputs: list[AnalysisOutput] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                outputs.append(AnalysisOutput.model_validate(item))
            except Exception:
                continue
        return outputs

    def _save_jobs(self, jobs: list[AnalysisJob]):
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self.jobs_file.write_text(
            json.dumps([job.model_dump(mode="json") for job in jobs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_outputs(self, outputs: list[AnalysisOutput]):
        self.outputs_file.parent.mkdir(parents=True, exist_ok=True)
        self.outputs_file.write_text(
            json.dumps([output.model_dump(mode="json") for output in outputs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
