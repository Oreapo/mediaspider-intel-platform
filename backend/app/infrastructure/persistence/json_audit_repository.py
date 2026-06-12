from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.audit import AuditEvent
from ...domain.repositories.audit_repository import AuditRepository


class JsonAuditRepository(AuditRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

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
        events = self._filter_events(
            target_type=target_type,
            target_id=target_id,
            actor_username=actor_username,
            action=action,
            query=query,
            created_from=created_from,
            created_to=created_to,
        )
        if offset:
            events = events[offset:]
        if limit is not None:
            events = events[:limit]
        return events

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
        return len(
            self._filter_events(
                target_type=target_type,
                target_id=target_id,
                actor_username=actor_username,
                action=action,
                query=query,
                created_from=created_from,
                created_to=created_to,
            )
        )

    def _filter_events(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        actor_username: str | None = None,
        action: str | None = None,
        query: str = "",
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[AuditEvent]:
        events = self._load_all()
        if target_type:
            events = [event for event in events if event.target_type == target_type]
        if target_id:
            events = [event for event in events if event.target_id == target_id]
        if actor_username:
            events = [event for event in events if event.actor_username == actor_username]
        if action:
            events = [event for event in events if event.action == action]
        if created_from:
            events = [event for event in events if event.created_at.isoformat() >= created_from]
        if created_to:
            events = [event for event in events if event.created_at.isoformat() <= created_to]
        normalized_query = query.strip().lower()
        if normalized_query:
            events = [event for event in events if normalized_query in self._search_text(event)]
        return sorted(events, key=lambda event: event.created_at, reverse=True)

    def save_event(self, event: AuditEvent) -> AuditEvent:
        events = self._load_all()
        events.append(event)
        self._save_all(events)
        return event

    def _search_text(self, event: AuditEvent) -> str:
        return " ".join(
            [
                event.id,
                event.action,
                event.actor_username,
                event.actor_role,
                event.target_type,
                event.target_id,
                event.summary,
                json.dumps(event.metadata_json, ensure_ascii=False, sort_keys=True),
            ]
        ).lower()

    def _load_all(self) -> list[AuditEvent]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        events: list[AuditEvent] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                events.append(AuditEvent.model_validate(item))
            except Exception:
                continue
        return events

    def _save_all(self, events: list[AuditEvent]) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([event.model_dump(mode="json") for event in events], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
