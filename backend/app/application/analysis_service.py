from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from ..domain.models.analysis import AnalysisJob, AnalysisJobStatus, AnalysisOutput, AnalysisScope
from ..domain.repositories.analysis_repository import AnalysisRepository
from ..domain.models.dataset import Dataset
from .dataset_service import DatasetService


class AnalysisService:
    def __init__(self, repository: AnalysisRepository, dataset_service: DatasetService):
        self.repository = repository
        self.dataset_service = dataset_service

    def list_jobs(self) -> list[AnalysisJob]:
        return self.repository.list_jobs()

    def get_job(self, job_id: str) -> AnalysisJob | None:
        return self.repository.get_job(job_id)

    def get_outputs(self, job_id: str) -> list[AnalysisOutput]:
        return self.repository.list_outputs(job_id)

    def create_job(
        self,
        *,
        dataset_id: str,
        analysis_scope: AnalysisScope,
        analysis_type: str,
        parameters_json: dict[str, Any] | None = None,
    ) -> AnalysisJob:
        dataset = self.dataset_service.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        now = datetime.utcnow().isoformat()
        job = AnalysisJob(
            dataset_id=dataset_id,
            analysis_scope=analysis_scope,
            analysis_type=analysis_type,
            status=AnalysisJobStatus.RUNNING,
            parameters_json=parameters_json or {},
            started_at=now,
        )
        self.repository.save_job(job)

        try:
            output = self._build_output(job, dataset)
            self.repository.save_output(output)
            finished = job.model_copy(
                update={
                    "status": AnalysisJobStatus.SUCCEEDED,
                    "finished_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow(),
                }
            )
            self.repository.save_job(finished)
            return finished
        except Exception as exc:
            failed = job.model_copy(
                update={
                    "status": AnalysisJobStatus.FAILED,
                    "finished_at": datetime.utcnow().isoformat(),
                    "error_message": str(exc),
                    "updated_at": datetime.utcnow(),
                }
            )
            self.repository.save_job(failed)
            return failed

    def _build_output(self, job: AnalysisJob, dataset: Dataset) -> AnalysisOutput:
        preview = self.dataset_service.preview_dataset(dataset.id, limit=200)
        columns = preview.get("columns", [])
        rows = preview.get("rows", [])
        records = [dict(zip(columns, row)) for row in rows]

        top_fields = self._top_fields(records)
        top_terms = self._top_terms(records)
        payload = {
          "dataset_id": dataset.id,
          "dataset_name": dataset.dataset_name,
          "platform": dataset.source_platform.value if hasattr(dataset.source_platform, "value") else str(dataset.source_platform),
          "analysis_scope": job.analysis_scope.value,
          "analysis_type": job.analysis_type,
          "summary_cards": [
              {"label": "Record Count", "value": dataset.record_count},
              {"label": "Field Count", "value": len(columns)},
              {"label": "Top Fields", "value": ", ".join(top_fields) or "-"},
          ],
          "top_terms": top_terms,
          "columns": columns,
        }
        return AnalysisOutput(
            analysis_job_id=job.id,
            output_type="summary",
            title=f"{dataset.dataset_name} · {job.analysis_type}",
            summary=f"Generated {job.analysis_scope.value} analysis for dataset {dataset.dataset_name}",
            payload_json=payload,
        )

    def _top_fields(self, records: list[dict[str, Any]]) -> list[str]:
        counter: Counter[str] = Counter()
        for row in records:
            for key, value in row.items():
                if str(value).strip():
                    counter[key] += 1
        return [key for key, _count in counter.most_common(5)]

    def _top_terms(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for row in records:
            for value in row.values():
                text = str(value).strip()
                if not text:
                    continue
                for token in self._tokenize(text):
                    counter[token] += 1
        return [
            {"term": term, "count": count}
            for term, count in counter.most_common(10)
        ]

    def _tokenize(self, text: str) -> list[str]:
        clean = text.replace("\n", " ").replace("，", " ").replace(",", " ").replace("|", " ")
        raw_tokens = [token.strip() for token in clean.split(" ")]
        return [token for token in raw_tokens if len(token) >= 2][:30]
