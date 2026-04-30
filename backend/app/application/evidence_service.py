from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.models.case import CaseLinkType
from ..domain.models.evidence import EvidencePacket
from ..domain.repositories.evidence_repository import EvidenceRepository
from .case_service import CaseService


class EvidenceService:
    def __init__(self, repository: EvidenceRepository, case_service: CaseService, storage_root: Path):
        self.repository = repository
        self.case_service = case_service
        self.storage_root = storage_root
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def list_packets(self) -> list[EvidencePacket]:
        return self.repository.list_packets()

    def get_packet(self, packet_id: str) -> EvidencePacket | None:
        return self.repository.get_packet(packet_id)

    def generate_packet(self, *, case_id: str, packet_name: str) -> EvidencePacket:
        case_detail = self.case_service.get_case_detail(case_id)
        if case_detail is None:
            raise ValueError(f"Case {case_id} not found")

        packet = EvidencePacket(
            case_id=case_id,
            packet_name=packet_name,
            storage_uri="",
            manifest_json={},
        )
        manifest = self._build_manifest(packet.id, packet_name, case_detail)
        storage_uri = f"{packet.id}.json"
        self._write_manifest(storage_uri, manifest)
        saved = self.repository.save_packet(
            packet.model_copy(
                update={
                    "storage_uri": storage_uri,
                    "manifest_json": manifest,
                    "updated_at": datetime.utcnow(),
                }
            )
        )
        self.case_service.add_link(
            case_id=case_id,
            link_type=CaseLinkType.EVIDENCE_PACKET,
            target_id=saved.id,
            label=packet_name,
            source_ref_json={"packet_id": saved.id, "storage_uri": storage_uri},
        )
        return saved

    def delete_packet(self, packet_id: str, delete_storage: bool = False) -> bool:
        packet = self.repository.get_packet(packet_id)
        if packet is None:
            return False
        deleted = self.repository.delete_packet(packet_id)
        if deleted and delete_storage:
            path = self.resolve_packet_path(packet.storage_uri)
            if path.exists():
                path.unlink()
        return deleted

    def resolve_packet_path(self, storage_uri: str) -> Path:
        file_path = (self.storage_root / storage_uri).resolve()
        file_path.relative_to(self.storage_root.resolve())
        return file_path

    def _write_manifest(self, storage_uri: str, manifest: dict[str, Any]) -> None:
        path = self.resolve_packet_path(storage_uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_manifest(
        self,
        packet_id: str,
        packet_name: str,
        case_detail: dict[str, Any],
    ) -> dict[str, Any]:
        objects = case_detail["objects"]
        return {
            "schema_version": "evidence_packet.v1",
            "packet_id": packet_id,
            "packet_name": packet_name,
            "exported_at": datetime.utcnow().isoformat(),
            "case": case_detail["case"],
            "summary": {
                "dataset_count": len(objects["datasets"]),
                "signal_count": len(objects["signals"]),
                "entity_count": len(objects["entities"]),
                "analysis_output_count": len(objects["analysis_outputs"]),
                "note_count": len(case_detail["notes"]),
                "timeline_event_count": len(case_detail["timeline"]),
            },
            "source_records": self._source_records(objects),
            "signals": objects["signals"],
            "entities": objects["entities"],
            "analysis_outputs": objects["analysis_outputs"],
            "notes": case_detail["notes"],
            "timeline": case_detail["timeline"],
            "links": case_detail["links"],
        }

    def _source_records(self, objects: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for dataset in objects["datasets"]:
            records.append(
                {
                    "source_type": "dataset",
                    "dataset_id": dataset["id"],
                    "dataset_name": dataset["dataset_name"],
                    "source_platform": dataset["source_platform"],
                    "storage_uri": dataset["storage_uri"],
                    "record_count": dataset["record_count"],
                    "snapshot_time": dataset["snapshot_time"],
                }
            )
        for signal in objects["signals"]:
            payload = signal.get("payload_json") or {}
            source_ref = payload.get("source_ref") if isinstance(payload, dict) else {}
            records.append(
                {
                    "source_type": "signal",
                    "signal_id": signal["id"],
                    "dataset_id": signal["dataset_id"],
                    "summary": signal["summary"],
                    "risk_level": signal["risk_level"],
                    "source_ref": source_ref if isinstance(source_ref, dict) else {},
                }
            )
        return records
