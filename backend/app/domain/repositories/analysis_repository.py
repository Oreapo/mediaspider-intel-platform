from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.analysis import AnalysisJob, AnalysisOutput


class AnalysisRepository(ABC):
    @abstractmethod
    def list_jobs(self) -> list[AnalysisJob]:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: str) -> AnalysisJob | None:
        raise NotImplementedError

    @abstractmethod
    def save_job(self, job: AnalysisJob) -> AnalysisJob:
        raise NotImplementedError

    @abstractmethod
    def list_outputs(self, job_id: str) -> list[AnalysisOutput]:
        raise NotImplementedError

    @abstractmethod
    def save_output(self, output: AnalysisOutput) -> AnalysisOutput:
        raise NotImplementedError
