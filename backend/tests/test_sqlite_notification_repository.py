from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.domain.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
    NotificationRule,
)
from app.domain.models.signal import RiskLevel
from app.infrastructure.persistence.sqlite_notification_repository import SQLiteNotificationRepository


def _rule(rule_id: str, updated_at: datetime) -> NotificationRule:
    return NotificationRule(
        id=rule_id,
        rule_name=f"Rule {rule_id}",
        enabled=True,
        event_type=NotificationEventType.SCHEDULED_DIGEST,
        risk_level_threshold=RiskLevel.HIGH,
        scenario_types=["lead_diversion"],
        platforms=["xhs"],
        channels=[NotificationChannel.INTERNAL_INBOX, NotificationChannel.EMAIL],
        cron_expr="* * * * *",
        cooldown_minutes=30,
        channel_config_json={"email_recipients": ["risk@example.com"]},
        last_executed_at=updated_at.isoformat(),
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_sqlite_notification_repository_rules_and_deliveries(tmp_path):
    repository = SQLiteNotificationRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = _rule("nr_first", now)
    second = _rule("nr_second", now + timedelta(minutes=1))

    repository.save_rule(first)
    repository.save_rule(second)

    assert repository.get_rule("nr_first") == first
    assert [item.id for item in repository.list_rules()] == ["nr_second", "nr_first"]

    updated = first.model_copy(update={"enabled": False, "updated_at": now + timedelta(minutes=2)})
    repository.save_rule(updated)
    assert repository.get_rule("nr_first").enabled is False

    delivery = NotificationDelivery(
        id="nd_1",
        rule_id="nr_first",
        target_type="signal",
        target_id="sig_1",
        channel=NotificationChannel.INTERNAL_INBOX,
        status=NotificationDeliveryStatus.SENT,
        payload_json={"event_count": 1},
        created_at=now,
        updated_at=now,
    )
    repository.save_delivery(delivery)
    assert repository.list_deliveries() == [delivery]

    assert repository.delete_rule("nr_second") is True
    assert repository.delete_rule("missing") is False


def test_app_container_can_switch_notification_repository_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "notifications.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_NOTIFICATION_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    rule = container.notification_service.create_rule(
        type(
            "Payload",
            (),
            {
                "model_dump": lambda self: {
                    "rule_name": "SQLite Notification",
                    "enabled": True,
                    "event_type": NotificationEventType.SCHEDULED_DIGEST,
                    "risk_level_threshold": RiskLevel.MEDIUM,
                    "scenario_types": [],
                    "platforms": [],
                    "channels": [NotificationChannel.INTERNAL_INBOX],
                    "cron_expr": "* * * * *",
                    "cooldown_minutes": 60,
                    "channel_config_json": {},
                }
            },
        )()
    )

    assert sqlite_path.exists()
    assert container.notification_service.get_rule(rule.id).rule_name == "SQLite Notification"


def test_sqlite_notification_repository_filters_counts_and_paginates(tmp_path):
    repository = SQLiteNotificationRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    deliveries = [
        NotificationDelivery(
            id="nd_sent",
            rule_id="nr_first",
            target_type="signal",
            target_id="sig_100%",
            channel=NotificationChannel.INTERNAL_INBOX,
            status=NotificationDeliveryStatus.SENT,
            payload_json={"summary": "Risk account alpha"},
            created_at=now,
            updated_at=now,
        ),
        NotificationDelivery(
            id="nd_failed",
            rule_id="nr_first",
            target_type="signal",
            target_id="sig_failed",
            channel=NotificationChannel.EMAIL,
            status=NotificationDeliveryStatus.FAILED,
            payload_json={"summary": "Email delivery"},
            error_message="SMTP unavailable",
            created_at=now + timedelta(minutes=1),
            updated_at=now + timedelta(minutes=1),
        ),
        NotificationDelivery(
            id="nd_skipped",
            rule_id="nr_second",
            target_type="scheduled_digest",
            target_id="digest_1",
            channel=NotificationChannel.INTERNAL_INBOX,
            status=NotificationDeliveryStatus.SKIPPED,
            payload_json={"reason": "no_matching_events", "_inbox": {"read_at": now.isoformat()}},
            created_at=now + timedelta(minutes=2),
            updated_at=now + timedelta(minutes=2),
        ),
    ]
    for delivery in deliveries:
        repository.save_delivery(delivery)

    assert [item.id for item in repository.list_deliveries(rule_id="nr_first")] == [
        "nd_failed",
        "nd_sent",
    ]
    assert [item.id for item in repository.list_deliveries(status=NotificationDeliveryStatus.FAILED)] == [
        "nd_failed"
    ]
    assert [item.id for item in repository.list_deliveries(channel=NotificationChannel.EMAIL)] == [
        "nd_failed"
    ]
    assert [item.id for item in repository.list_deliveries(target_type="SIGNAL")] == [
        "nd_failed",
        "nd_sent",
    ]
    assert [item.id for item in repository.list_deliveries(query="smtp unavailable")] == ["nd_failed"]
    assert [item.id for item in repository.list_deliveries(query="100%")] == ["nd_sent"]
    assert [item.id for item in repository.list_deliveries(target_id="sig_failed")] == ["nd_failed"]
    assert [item.id for item in repository.list_deliveries(is_read=True)] == ["nd_skipped"]
    assert [item.id for item in repository.list_deliveries(is_read=False)] == ["nd_failed", "nd_sent"]
    assert [item.id for item in repository.list_deliveries(limit=1, offset=1)] == ["nd_failed"]
    assert repository.count_deliveries(channel=NotificationChannel.INTERNAL_INBOX) == 2
    assert repository.count_deliveries(query="no_matching_events") == 1
    assert repository.count_deliveries(is_read=False) == 2
    assert repository.get_delivery("nd_failed") == deliveries[1]
    assert repository.get_delivery("missing") is None
