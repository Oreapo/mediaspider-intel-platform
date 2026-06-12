from __future__ import annotations

from backend.app.domain.models.audit import AuditEvent
from backend.app.infrastructure.persistence.sqlite_audit_repository import SQLiteAuditRepository


def test_sqlite_audit_repository_counts_filtered_events_before_pagination(tmp_path):
    repository = SQLiteAuditRepository(tmp_path / "audit.sqlite3")
    repository.save_event(
        AuditEvent(
            action="task.create",
            actor_username="analyst",
            actor_role="analyst",
            target_type="task",
            target_id="task-1",
            summary="Created first task",
        )
    )
    repository.save_event(
        AuditEvent(
            action="task.update",
            actor_username="analyst",
            actor_role="analyst",
            target_type="task",
            target_id="task-1",
            summary="Updated first task",
        )
    )
    repository.save_event(
        AuditEvent(
            action="case.create",
            actor_username="operator",
            actor_role="operator",
            target_type="case",
            target_id="case-1",
            summary="Created first case",
        )
    )

    second_page = repository.list_events(target_type="task", limit=1, offset=1)
    without_limit = repository.list_events(offset=1)

    assert len(second_page) == 1
    assert len(without_limit) == 2
    assert repository.count_events(target_type="task") == 2
    assert repository.count_events(actor_username="operator") == 1
    assert repository.count_events(query="updated") == 1


def test_sqlite_audit_repository_upserts_existing_event(tmp_path):
    repository = SQLiteAuditRepository(tmp_path / "audit.sqlite3")
    event = AuditEvent(
        id="aud_repeatable",
        action="report.create",
        actor_username="analyst",
        actor_role="analyst",
        target_type="report",
        target_id="report-1",
        summary="Created report",
    )

    repository.save_event(event)
    updated = event.model_copy(update={"summary": "Updated report audit"})
    repository.save_event(updated)

    assert repository.count_events(target_id="report-1") == 1
    assert repository.list_events(target_id="report-1") == [updated]
