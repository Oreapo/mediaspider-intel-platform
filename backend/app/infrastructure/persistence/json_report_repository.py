from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.report import Report
from ...domain.repositories.report_repository import ReportRepository


class JsonReportRepository(ReportRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_reports(self) -> list[Report]:
        return sorted(self._load_all(), key=lambda report: report.updated_at, reverse=True)

    def get_report(self, report_id: str) -> Report | None:
        for report in self._load_all():
            if report.id == report_id:
                return report
        return None

    def save_report(self, report: Report) -> Report:
        reports = self._load_all()
        replaced = False
        for index, existing in enumerate(reports):
            if existing.id == report.id:
                reports[index] = report
                replaced = True
                break
        if not replaced:
            reports.append(report)
        self._save_all(reports)
        return report

    def delete_report(self, report_id: str) -> bool:
        reports = self._load_all()
        filtered = [report for report in reports if report.id != report_id]
        if len(filtered) == len(reports):
            return False
        self._save_all(filtered)
        return True

    def _load_all(self) -> list[Report]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        reports: list[Report] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                reports.append(Report.model_validate(item))
            except Exception:
                continue
        return reports

    def _save_all(self, reports: list[Report]) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([report.model_dump(mode="json") for report in reports], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
