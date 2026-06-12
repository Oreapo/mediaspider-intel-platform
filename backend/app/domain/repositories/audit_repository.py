from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.audit import AuditEvent


class AuditRepository(ABC):
    @abstractmethod
    def list_events(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_username: str | None = None,
        action: str | None = None,
        query: str = "",
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[AuditEvent]:
        raise NotImplementedError

    @abstractmethod
    def count_events(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_username: str | None = None,
        action: str | None = None,
        query: str = "",
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def save_event(self, event: AuditEvent) -> AuditEvent:
        raise NotImplementedError
