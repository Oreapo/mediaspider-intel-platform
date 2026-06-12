from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.evidence import EvidencePacket


class EvidenceRepository(ABC):
    @abstractmethod
    def list_packets(self, *, limit: int | None = None, offset: int = 0) -> list[EvidencePacket]:
        raise NotImplementedError

    @abstractmethod
    def count_packets(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_packet(self, packet_id: str) -> EvidencePacket | None:
        raise NotImplementedError

    @abstractmethod
    def save_packet(self, packet: EvidencePacket) -> EvidencePacket:
        raise NotImplementedError

    @abstractmethod
    def delete_packet(self, packet_id: str) -> bool:
        raise NotImplementedError
