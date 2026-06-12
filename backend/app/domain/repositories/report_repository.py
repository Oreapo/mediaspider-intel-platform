from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.report import Report


class ReportRepository(ABC):
    @abstractmethod
    def list_reports(self, *, limit: int | None = None, offset: int = 0) -> list[Report]:
        raise NotImplementedError

    @abstractmethod
    def count_reports(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_report(self, report_id: str) -> Report | None:
        raise NotImplementedError

    @abstractmethod
    def save_report(self, report: Report) -> Report:
        raise NotImplementedError

    @abstractmethod
    def delete_report(self, report_id: str) -> bool:
        raise NotImplementedError
