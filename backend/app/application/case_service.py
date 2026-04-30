from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from ..api.schemas.case import CaseCreateRequest, CaseUpdateRequest
from ..domain.models.case import Case, CaseLink, CaseLinkType, CaseNote
from ..domain.repositories.case_repository import CaseRepository
from .analysis_service import AnalysisService
from .dataset_service import DatasetService
from .entity_service import EntityService
from .signal_service import SignalService


class CaseService:
    def __init__(
        self,
        repository: CaseRepository,
        dataset_service: DatasetService,
        signal_service: SignalService,
        entity_service: EntityService,
        analysis_service: AnalysisService,
    ):
        self.repository = repository
        self.dataset_service = dataset_service
        self.signal_service = signal_service
        self.entity_service = entity_service
        self.analysis_service = analysis_service
        self.evidence_packet_resolver: Callable[[str], Any | None] | None = None

    def set_evidence_packet_resolver(self, resolver: Callable[[str], Any | None]) -> None:
        self.evidence_packet_resolver = resolver

    def list_cases(self) -> list[Case]:
        return self.repository.list_cases()

    def get_case(self, case_id: str) -> Case | None:
        return self.repository.get_case(case_id)

    def create_case(self, payload: CaseCreateRequest) -> Case:
        case = Case(**payload.model_dump())
        return self.repository.save_case(case)

    def update_case(self, case_id: str, payload: CaseUpdateRequest) -> Case:
        case = self.repository.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        updated = case.model_copy(
            update={
                **payload.model_dump(exclude_unset=True),
                "updated_at": datetime.utcnow(),
            }
        )
        return self.repository.save_case(updated)

    def delete_case(self, case_id: str) -> bool:
        return self.repository.delete_case(case_id)

    def get_case_detail(self, case_id: str) -> dict[str, Any] | None:
        case = self.repository.get_case(case_id)
        if case is None:
            return None
        links = self.repository.list_links(case_id)
        notes = self.repository.list_notes(case_id)
        resolved = self._resolve_links(links)
        return {
            "case": case.model_dump(mode="json"),
            "links": [link.model_dump(mode="json") for link in links],
            "notes": [note.model_dump(mode="json") for note in notes],
            "objects": resolved,
            "timeline": self.build_timeline(case_id),
        }

    def add_link(
        self,
        *,
        case_id: str,
        link_type: CaseLinkType,
        target_id: str,
        label: str = "",
        source_ref_json: dict[str, Any] | None = None,
    ) -> CaseLink:
        case = self.repository.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        self._validate_target(link_type, target_id)
        duplicate = self._find_duplicate_link(case_id, link_type, target_id)
        if duplicate is not None:
            merged = duplicate.model_copy(
                update={
                    "label": label or duplicate.label,
                    "source_ref_json": {**duplicate.source_ref_json, **(source_ref_json or {})},
                    "updated_at": datetime.utcnow(),
                }
            )
            return self.repository.save_link(merged)
        link = CaseLink(
            case_id=case_id,
            link_type=link_type,
            target_id=target_id,
            label=label,
            source_ref_json=source_ref_json or {},
        )
        saved = self.repository.save_link(link)
        self.repository.save_case(case.model_copy(update={"updated_at": datetime.utcnow()}))
        return saved

    def delete_link(self, link_id: str) -> bool:
        return self.repository.delete_link(link_id)

    def add_note(
        self,
        *,
        case_id: str,
        author: str = "",
        body: str,
        note_type: str = "investigation",
    ) -> CaseNote:
        case = self.repository.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        note = CaseNote(case_id=case_id, author=author, body=body, note_type=note_type)
        saved = self.repository.save_note(note)
        self.repository.save_case(case.model_copy(update={"updated_at": datetime.utcnow()}))
        return saved

    def delete_note(self, note_id: str) -> bool:
        return self.repository.delete_note(note_id)

    def build_timeline(self, case_id: str) -> list[dict[str, Any]]:
        case = self.repository.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        items: list[dict[str, Any]] = [
            {
                "event_type": "case_created",
                "event_time": case.created_at.isoformat(),
                "target_type": "case",
                "target_id": case.id,
                "title": case.case_name,
                "source_ref": {"case_id": case.id},
            }
        ]
        for link in self.repository.list_links(case_id):
            resolved = self._resolve_link(link)
            event_time = resolved.get("created_at") or link.created_at.isoformat()
            items.append(
                {
                    "event_type": f"{link.link_type.value}_attached",
                    "event_time": event_time,
                    "target_type": link.link_type.value,
                    "target_id": link.target_id,
                    "title": self._timeline_title(link, resolved),
                    "source_ref": {
                        "case_id": case_id,
                        "case_link_id": link.id,
                        **link.source_ref_json,
                    },
                }
            )
        for note in self.repository.list_notes(case_id):
            items.append(
                {
                    "event_type": "note_added",
                    "event_time": note.created_at.isoformat(),
                    "target_type": "case_note",
                    "target_id": note.id,
                    "title": note.body[:120],
                    "source_ref": {"case_id": case_id, "note_id": note.id, "author": note.author},
                }
            )
        return sorted(items, key=lambda item: (item["event_time"], item["event_type"], item["target_id"]))

    def _validate_target(self, link_type: CaseLinkType, target_id: str) -> None:
        if link_type == CaseLinkType.DATASET and self.dataset_service.get_dataset(target_id) is None:
            raise ValueError(f"Dataset {target_id} not found")
        if link_type == CaseLinkType.SIGNAL and self.signal_service.get_signal(target_id) is None:
            raise ValueError(f"Signal {target_id} not found")
        if link_type == CaseLinkType.ENTITY and self.entity_service.get_entity(target_id) is None:
            raise ValueError(f"Entity {target_id} not found")
        if link_type == CaseLinkType.ANALYSIS_OUTPUT and self._get_analysis_output(target_id) is None:
            raise ValueError(f"Analysis output {target_id} not found")
        if link_type == CaseLinkType.EVIDENCE_PACKET:
            if self.evidence_packet_resolver is None or self.evidence_packet_resolver(target_id) is None:
                raise ValueError(f"Evidence packet {target_id} not found")

    def _resolve_links(self, links: list[CaseLink]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {
            "datasets": [],
            "signals": [],
            "entities": [],
            "analysis_outputs": [],
            "evidence_packets": [],
        }
        for link in links:
            resolved = self._resolve_link(link)
            if not resolved:
                continue
            if link.link_type == CaseLinkType.DATASET:
                grouped["datasets"].append(resolved)
            elif link.link_type == CaseLinkType.SIGNAL:
                grouped["signals"].append(resolved)
            elif link.link_type == CaseLinkType.ENTITY:
                grouped["entities"].append(resolved)
            elif link.link_type == CaseLinkType.ANALYSIS_OUTPUT:
                grouped["analysis_outputs"].append(resolved)
            elif link.link_type == CaseLinkType.EVIDENCE_PACKET:
                grouped["evidence_packets"].append(resolved)
        return grouped

    def _resolve_link(self, link: CaseLink) -> dict[str, Any]:
        if link.link_type == CaseLinkType.DATASET:
            dataset = self.dataset_service.get_dataset(link.target_id)
            return dataset.model_dump(mode="json") if dataset else {}
        if link.link_type == CaseLinkType.SIGNAL:
            signal = self.signal_service.get_signal(link.target_id)
            return signal.model_dump(mode="json") if signal else {}
        if link.link_type == CaseLinkType.ENTITY:
            entity = self.entity_service.get_entity(link.target_id)
            return entity.model_dump(mode="json") if entity else {}
        if link.link_type == CaseLinkType.ANALYSIS_OUTPUT:
            output = self._get_analysis_output(link.target_id)
            return output.model_dump(mode="json") if output else {}
        if link.link_type == CaseLinkType.EVIDENCE_PACKET and self.evidence_packet_resolver is not None:
            packet = self.evidence_packet_resolver(link.target_id)
            return packet.model_dump(mode="json") if packet else {}
        return {}

    def _get_analysis_output(self, output_id: str):
        for job in self.analysis_service.list_jobs():
            for output in self.analysis_service.get_outputs(job.id):
                if output.id == output_id:
                    return output
        return None

    def _find_duplicate_link(self, case_id: str, link_type: CaseLinkType, target_id: str) -> CaseLink | None:
        for link in self.repository.list_links(case_id):
            if link.link_type == link_type and link.target_id == target_id:
                return link
        return None

    def _timeline_title(self, link: CaseLink, resolved: dict[str, Any]) -> str:
        if link.label:
            return link.label
        if link.link_type == CaseLinkType.DATASET:
            return str(resolved.get("dataset_name") or link.target_id)
        if link.link_type == CaseLinkType.SIGNAL:
            return str(resolved.get("summary") or link.target_id)
        if link.link_type == CaseLinkType.ENTITY:
            return str(resolved.get("display_name") or link.target_id)
        if link.link_type == CaseLinkType.ANALYSIS_OUTPUT:
            return str(resolved.get("title") or link.target_id)
        if link.link_type == CaseLinkType.EVIDENCE_PACKET:
            return str(resolved.get("packet_name") or link.target_id)
        return link.target_id
