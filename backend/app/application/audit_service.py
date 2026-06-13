from __future__ import annotations

from typing import Any

from .auth_service import AuthUser
from ..domain.models.audit import AuditEvent
from ..domain.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository):
        self.repository = repository

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
        return self.repository.list_events(
            target_type=target_type,
            target_id=target_id,
            actor_username=actor_username,
            action=action,
            query=query,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )

    def list_events_page(
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
    ) -> tuple[list[AuditEvent], int]:
        filters = {
            "target_type": target_type,
            "target_id": target_id,
            "actor_username": actor_username,
            "action": action,
            "query": query,
            "created_from": created_from,
            "created_to": created_to,
        }
        events = self.repository.list_events(**filters, limit=limit, offset=offset)
        total = self.repository.count_events(**filters)
        return events, total

    def record(
        self,
        *,
        action: str,
        actor: AuthUser,
        target_type: str,
        target_id: str,
        summary: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            action=action,
            actor_username=actor.username,
            actor_role=actor.role,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            metadata_json=metadata_json or {},
        )
        return self.repository.save_event(event)

    def record_system(
        self,
        *,
        action: str,
        target_type: str,
        target_id: str,
        summary: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return self.record(
            action=action,
            actor=AuthUser(username="system", role="system", display_name="System"),
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            metadata_json=metadata_json,
        )
