from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.schemas.report import ReportGenerateRequest
from ..domain.models.report import Report
from ..domain.repositories.report_repository import ReportRepository
from .case_service import CaseService


class ReportService:
    def __init__(self, repository: ReportRepository, case_service: CaseService, storage_root: Path):
        self.repository = repository
        self.case_service = case_service
        self.storage_root = storage_root
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def list_reports(self) -> list[Report]:
        return self.repository.list_reports()

    def get_report(self, report_id: str) -> Report | None:
        return self.repository.get_report(report_id)

    def generate_report(self, payload: ReportGenerateRequest) -> Report:
        case_detail = self.case_service.get_case_detail(payload.case_id)
        if case_detail is None:
            raise ValueError(f"Case {payload.case_id} not found")

        report = Report(
            case_id=payload.case_id,
            report_name=payload.report_name,
            report_type=payload.report_type,
        )
        summary = self._build_summary(case_detail)
        content = self._render_markdown(report, case_detail, summary)
        storage_uri = f"{report.id}.md"
        self._write_report(storage_uri, content)
        saved = report.model_copy(
            update={
                "storage_uri": storage_uri,
                "content_markdown": content,
                "summary_json": summary,
                "updated_at": datetime.utcnow(),
            }
        )
        return self.repository.save_report(saved)

    def delete_report(self, report_id: str, delete_storage: bool = False) -> bool:
        report = self.repository.get_report(report_id)
        if report is None:
            return False
        deleted = self.repository.delete_report(report_id)
        if deleted and delete_storage and report.storage_uri:
            path = self.resolve_report_path(report.storage_uri)
            if path.exists():
                path.unlink()
        return deleted

    def resolve_report_path(self, storage_uri: str) -> Path:
        file_path = (self.storage_root / storage_uri).resolve()
        file_path.relative_to(self.storage_root.resolve())
        return file_path

    def _write_report(self, storage_uri: str, content: str) -> None:
        path = self.resolve_report_path(storage_uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _build_summary(self, case_detail: dict[str, Any]) -> dict[str, Any]:
        objects = case_detail["objects"]
        risk_levels: dict[str, int] = {}
        for signal in objects["signals"]:
            level = str(signal.get("risk_level") or "unknown")
            risk_levels[level] = risk_levels.get(level, 0) + 1
        platforms = sorted(
            {
                str(dataset.get("source_platform"))
                for dataset in objects["datasets"]
                if dataset.get("source_platform")
            }
        )
        source_refs = []
        for signal in objects["signals"]:
            payload = signal.get("payload_json") or {}
            source_ref = payload.get("source_ref") if isinstance(payload, dict) else None
            if isinstance(source_ref, dict):
                source_refs.append(source_ref)
        return {
            "case_id": case_detail["case"]["id"],
            "case_name": case_detail["case"]["case_name"],
            "generated_at": datetime.utcnow().isoformat(),
            "platforms": platforms,
            "risk_levels": risk_levels,
            "dataset_count": len(objects["datasets"]),
            "signal_count": len(objects["signals"]),
            "entity_count": len(objects["entities"]),
            "analysis_output_count": len(objects["analysis_outputs"]),
            "evidence_packet_count": len(objects["evidence_packets"]),
            "note_count": len(case_detail["notes"]),
            "timeline_event_count": len(case_detail["timeline"]),
            "source_refs": source_refs,
        }

    def _render_markdown(
        self,
        report: Report,
        case_detail: dict[str, Any],
        summary: dict[str, Any],
    ) -> str:
        case = case_detail["case"]
        objects = case_detail["objects"]
        lines = [
            f"# {self._md(report.report_name)}",
            "",
            "## Case",
            "",
            f"- Case: {self._md(case['case_name'])}",
            f"- Type: {self._md(case.get('case_type') or '-')}",
            f"- Status: {self._md(case.get('status') or '-')}",
            f"- Priority: {self._md(case.get('priority') or '-')}",
            f"- Owner: {self._md(case.get('owner') or '-')}",
            f"- Generated at: {summary['generated_at']}",
            "",
            "## Executive Summary",
            "",
            self._md(case.get("summary") or "No case summary provided."),
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Datasets | {summary['dataset_count']} |",
            f"| Signals | {summary['signal_count']} |",
            f"| Entities | {summary['entity_count']} |",
            f"| Evidence packets | {summary['evidence_packet_count']} |",
            f"| Notes | {summary['note_count']} |",
            "",
            "## Risk Signals",
            "",
        ]
        if objects["signals"]:
            for signal in objects["signals"]:
                source_ref = self._source_ref(signal)
                lines.extend(
                    [
                        f"- **{self._md(signal.get('risk_level') or '-')}** · {self._md(signal.get('summary') or signal['id'])}",
                        f"  - Signal: `{signal['id']}` · Source: `{self._md(signal.get('signal_source') or '-')}`",
                        f"  - Trace: `{self._md(source_ref)}`",
                    ]
                )
        else:
            lines.append("- No linked signals.")
        lines.extend(["", "## Entities", ""])
        if objects["entities"]:
            for entity in objects["entities"]:
                lines.append(
                    f"- {self._md(entity.get('display_name') or entity['id'])} · {self._md(entity.get('entity_type') or '-')} · risk {entity.get('risk_score', 0)}"
                )
        else:
            lines.append("- No linked entities.")
        lines.extend(["", "## Evidence Packets", ""])
        if objects["evidence_packets"]:
            for packet in objects["evidence_packets"]:
                lines.append(f"- {self._md(packet.get('packet_name') or packet['id'])} · `{self._md(packet.get('storage_uri') or '-')}`")
        else:
            lines.append("- No evidence packets linked.")
        lines.extend(["", "## Analyst Notes", ""])
        if case_detail["notes"]:
            for note in case_detail["notes"]:
                lines.append(f"- {self._md(note.get('created_at') or '-')} · {self._md(note.get('author') or '-')}: {self._md(note.get('body') or '')}")
        else:
            lines.append("- No analyst notes.")
        lines.extend(["", "## Timeline", ""])
        for item in case_detail["timeline"]:
            lines.append(
                f"- {self._md(item.get('event_time') or '-')} · {self._md(item.get('event_type') or '-')} · {self._md(item.get('title') or '-')}"
            )
        lines.extend(["", "## Source Traceability", ""])
        if summary["source_refs"]:
            for index, source_ref in enumerate(summary["source_refs"], start=1):
                lines.append(f"{index}. `{self._md(str(source_ref))}`")
        else:
            lines.append("- No signal source refs available.")
        lines.append("")
        return "\n".join(lines)

    def _source_ref(self, signal: dict[str, Any]) -> str:
        payload = signal.get("payload_json") or {}
        source_ref = payload.get("source_ref") if isinstance(payload, dict) else {}
        return str(source_ref if isinstance(source_ref, dict) else {})

    def _md(self, value: Any) -> str:
        text = str(value)
        return re.sub(r"[\r\n]+", " ", text).strip()
