from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.evidence import EvidencePacket
from ...domain.repositories.evidence_repository import EvidenceRepository


class JsonEvidenceRepository(EvidenceRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_packets(self, *, limit: int | None = None, offset: int = 0) -> list[EvidencePacket]:
        packets = sorted(self._load_all(), key=lambda packet: packet.updated_at, reverse=True)
        if offset > 0:
            packets = packets[offset:]
        if limit is not None:
            packets = packets[:limit]
        return packets

    def count_packets(self) -> int:
        return len(self._load_all())

    def get_packet(self, packet_id: str) -> EvidencePacket | None:
        for packet in self._load_all():
            if packet.id == packet_id:
                return packet
        return None

    def save_packet(self, packet: EvidencePacket) -> EvidencePacket:
        packets = self._load_all()
        replaced = False
        for index, existing in enumerate(packets):
            if existing.id == packet.id:
                packets[index] = packet
                replaced = True
                break
        if not replaced:
            packets.append(packet)
        self._save_all(packets)
        return packet

    def delete_packet(self, packet_id: str) -> bool:
        packets = self._load_all()
        filtered = [packet for packet in packets if packet.id != packet_id]
        if len(filtered) == len(packets):
            return False
        self._save_all(filtered)
        return True

    def _load_all(self) -> list[EvidencePacket]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        packets: list[EvidencePacket] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                packets.append(EvidencePacket.model_validate(item))
            except Exception:
                continue
        return packets

    def _save_all(self, packets: list[EvidencePacket]) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([packet.model_dump(mode="json") for packet in packets], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
