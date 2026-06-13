from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
from app.application import notification_service
from app.main import app


def _create_signal(client: TestClient, risk_level: str = "high", platform: str = "xhs", scenario: str = "lead_diversion") -> str:
    dataset = client.post(
        "/api/datasets",
        json={
            "dataset_name": f"{platform} notification dataset",
            "dataset_type": "raw",
            "source_platform": platform,
            "scenario_type": scenario,
        },
    ).json()["dataset"]
    signal = client.post(
        "/api/signals",
        json={
            "dataset_id": dataset["id"],
            "signal_type": "contact_point_hit",
            "signal_source": "rule:contact_points",
            "risk_level": risk_level,
            "risk_score": 85 if risk_level == "high" else 30,
            "summary": "notification signal",
            "status": "confirmed",
            "payload_json": {"source_ref": {"dataset_id": dataset["id"], "row_index": 0}},
        },
    ).json()["signal"]
    return signal["id"]


def test_scheduled_digest_delivers_internal_inbox_and_updates_last_run(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        signal_id = _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "High risk digest",
                "enabled": True,
                "event_type": "scheduled_digest",
                "risk_level_threshold": "medium",
                "scenario_types": ["lead_diversion"],
                "platforms": ["xhs"],
                "channels": ["internal_inbox"],
                "cron_expr": "* * * * *",
                "cooldown_minutes": 60,
            },
        ).json()["rule"]
        now = datetime.utcnow().replace(second=0, microsecond=0)

        run_response = client.post("/api/notifications/run-scheduled", json={"now": now.isoformat()})
        assert run_response.status_code == 200
        result = run_response.json()["results"][0]
        assert result["rule_id"] == rule["id"]
        assert result["event_count"] == 1
        assert result["delivery_count"] == 1
        assert result["deliveries"][0]["target_type"] == "signal"
        assert result["deliveries"][0]["target_id"] == signal_id
        assert result["deliveries"][0]["status"] == "sent"

        updated = client.get(f"/api/notifications/rules/{rule['id']}").json()["rule"]
        assert updated["last_executed_at"] == now.isoformat()
    finally:
        set_container(original_container)


def test_disabled_rule_is_not_executed(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        _create_signal(client)
        client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Disabled digest",
                "enabled": False,
                "event_type": "scheduled_digest",
                "channels": ["internal_inbox"],
                "cron_expr": "* * * * *",
            },
        )
        response = client.post("/api/notifications/run-scheduled", json={"now": datetime.utcnow().isoformat()})
        assert response.status_code == 200
        assert response.json()["results"] == []
        assert client.get("/api/notifications/deliveries").json()["deliveries"] == []
    finally:
        set_container(original_container)


def test_digest_filters_by_risk_platform_and_scenario(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        _create_signal(client, risk_level="low", platform="xhs", scenario="lead_diversion")
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Critical only",
                "risk_level_threshold": "high",
                "scenario_types": ["lead_diversion"],
                "platforms": ["xhs"],
                "channels": ["internal_inbox"],
                "cron_expr": "* * * * *",
            },
        ).json()["rule"]
        response = client.post("/api/notifications/run-scheduled", json={"now": datetime.utcnow().isoformat()})
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["rule_id"] == rule["id"]
        assert result["event_count"] == 0
        assert result["deliveries"][0]["status"] == "skipped"
        assert result["deliveries"][0]["payload_json"]["reason"] == "no_matching_events"
    finally:
        set_container(original_container)


def test_cooldown_suppresses_duplicate_target(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        signal_id = _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Cooldown digest",
                "risk_level_threshold": "medium",
                "channels": ["internal_inbox"],
                "cron_expr": "* * * * *",
                "cooldown_minutes": 60,
            },
        ).json()["rule"]
        now = datetime.utcnow().replace(second=0, microsecond=0)
        first = client.post("/api/notifications/run-scheduled", json={"now": now.isoformat()})
        assert first.json()["results"][0]["event_count"] == 1

        client.patch(f"/api/notifications/rules/{rule['id']}", json={"last_executed_at": None})
        second = client.post(
            "/api/notifications/run-scheduled",
            json={"now": (now + timedelta(minutes=1)).isoformat()},
        )
        assert second.status_code == 200
        assert second.json()["results"][0]["event_count"] == 0
        deliveries = client.get("/api/notifications/deliveries").json()["deliveries"]
        sent_for_signal = [
            item for item in deliveries if item["target_type"] == "signal" and item["target_id"] == signal_id
        ]
        assert len(sent_for_signal) == 1
    finally:
        set_container(original_container)


def test_delivery_failure_is_recorded_and_last_run_updates(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Email failure digest",
                "risk_level_threshold": "medium",
                "channels": ["email"],
                "cron_expr": "* * * * *",
                "channel_config_json": {},
            },
        ).json()["rule"]
        now = datetime.utcnow().replace(second=0, microsecond=0)
        response = client.post("/api/notifications/run-scheduled", json={"now": now.isoformat()})
        assert response.status_code == 200
        delivery = response.json()["results"][0]["deliveries"][0]
        assert delivery["status"] == "failed"
        assert "email_recipients" in delivery["error_message"]

        updated = client.get(f"/api/notifications/rules/{rule['id']}").json()["rule"]
        assert updated["last_executed_at"] == now.isoformat()
    finally:
        set_container(original_container)


def test_email_delivery_sends_smtp_message(tmp_path, monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.started_tls = False
            self.login_args = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            self.started_tls = True

        def login(self, username, password):
            self.login_args = (username, password)

        def send_message(self, message):
            sent_messages.append(
                {
                    "host": self.host,
                    "port": self.port,
                    "timeout": self.timeout,
                    "started_tls": self.started_tls,
                    "login_args": self.login_args,
                    "message": message,
                }
            )

    monkeypatch.setattr(notification_service.smtplib, "SMTP", FakeSMTP)

    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        signal_id = _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "SMTP digest",
                "risk_level_threshold": "medium",
                "channels": ["email"],
                "cron_expr": "* * * * *",
                "channel_config_json": {
                    "email_recipients": ["risk@example.com"],
                    "smtp_host": "smtp.example.test",
                    "smtp_port": 2525,
                    "smtp_from": "platform@example.com",
                    "smtp_username": "user",
                    "smtp_password": "secret",
                    "smtp_use_tls": True,
                    "smtp_timeout_seconds": 3,
                },
            },
        ).json()["rule"]

        response = client.post(
            "/api/notifications/run-scheduled",
            json={"now": datetime.utcnow().replace(second=0, microsecond=0).isoformat()},
        )
        assert response.status_code == 200
        delivery = response.json()["results"][0]["deliveries"][0]
        assert delivery["rule_id"] == rule["id"]
        assert delivery["target_id"] == signal_id
        assert delivery["status"] == "sent"

        assert len(sent_messages) == 1
        sent = sent_messages[0]
        assert sent["host"] == "smtp.example.test"
        assert sent["port"] == 2525
        assert sent["timeout"] == 3
        assert sent["started_tls"] is True
        assert sent["login_args"] == ("user", "secret")
        message = sent["message"]
        assert message["From"] == "platform@example.com"
        assert message["To"] == "risk@example.com"
        assert "[MediaSpider] SMTP digest" in message["Subject"]
        assert "notification signal" in message.get_content()
    finally:
        set_container(original_container)


def test_failed_delivery_can_be_retried_after_configuration_fix(tmp_path, monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(notification_service.smtplib, "SMTP", FakeSMTP)

    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Retryable email digest",
                "risk_level_threshold": "medium",
                "channels": ["email"],
                "cron_expr": "* * * * *",
                "channel_config_json": {"email_recipients": ["risk@example.com"]},
            },
        ).json()["rule"]

        run_response = client.post(
            "/api/notifications/run-scheduled",
            json={"now": datetime.utcnow().replace(second=0, microsecond=0).isoformat()},
        )
        failed_delivery = run_response.json()["results"][0]["deliveries"][0]
        assert failed_delivery["status"] == "failed"
        assert failed_delivery["retry_count"] == 0
        assert failed_delivery["last_attempt_at"]

        client.patch(
            f"/api/notifications/rules/{rule['id']}",
            json={
                "channel_config_json": {
                    "email_recipients": ["risk@example.com"],
                    "smtp_host": "smtp.example.test",
                    "smtp_port": 2525,
                    "smtp_from": "platform@example.com",
                }
            },
        )

        retry_response = client.post(f"/api/notifications/deliveries/{failed_delivery['id']}/retry")
        assert retry_response.status_code == 200
        retried = retry_response.json()["delivery"]
        assert retried["id"] == failed_delivery["id"]
        assert retried["status"] == "sent"
        assert retried["error_message"] == ""
        assert retried["retry_count"] == 1
        assert retried["last_attempt_at"]
        assert len(sent_messages) == 1

        second_retry = client.post(f"/api/notifications/deliveries/{failed_delivery['id']}/retry")
        assert second_retry.status_code == 400
    finally:
        set_container(original_container)


def test_delivery_list_supports_filters_and_pagination(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        signal_id = _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Filterable digest",
                "risk_level_threshold": "medium",
                "channels": ["internal_inbox", "email"],
                "cron_expr": "* * * * *",
                "channel_config_json": {},
            },
        ).json()["rule"]

        response = client.post(
            "/api/notifications/run-scheduled",
            json={"now": datetime.utcnow().replace(second=0, microsecond=0).isoformat()},
        )
        assert response.status_code == 200

        failed = client.get("/api/notifications/deliveries", params={"status": "failed"}).json()["deliveries"]
        assert len(failed) == 1
        assert failed[0]["channel"] == "email"

        sent = client.get(
            "/api/notifications/deliveries",
            params={"rule_id": rule["id"], "channel": "internal_inbox", "q": signal_id},
        ).json()["deliveries"]
        assert len(sent) == 1
        assert sent[0]["status"] == "sent"
        assert sent[0]["target_id"] == signal_id

        paged_response = client.get("/api/notifications/deliveries", params={"limit": 1, "offset": 1})
        assert paged_response.status_code == 200
        paged = paged_response.json()
        assert len(paged["deliveries"]) == 1
        assert paged["total"] == 2

        filtered_page = client.get(
            "/api/notifications/deliveries",
            params={"status": "sent", "limit": 1, "offset": 0},
        ).json()
        assert len(filtered_page["deliveries"]) == 1
        assert filtered_page["total"] == 1
    finally:
        set_container(original_container)


def test_delivery_list_contract_is_preserved_in_sqlite_mode(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        signal_id = _create_signal(client)
        rule = client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "SQLite filterable digest",
                "risk_level_threshold": "medium",
                "channels": ["internal_inbox", "email"],
                "cron_expr": "* * * * *",
                "channel_config_json": {},
            },
        ).json()["rule"]
        run_response = client.post(
            "/api/notifications/run-scheduled",
            json={"now": datetime.utcnow().replace(second=0, microsecond=0).isoformat()},
        )
        assert run_response.status_code == 200

        response = client.get(
            "/api/notifications/deliveries",
            params={
                "rule_id": rule["id"],
                "status": "sent",
                "channel": "internal_inbox",
                "target_type": "signal",
                "q": signal_id,
                "limit": 1,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        assert set(response.json()) == {"deliveries", "total"}
        assert len(response.json()["deliveries"]) == 1
        assert response.json()["deliveries"][0]["target_id"] == signal_id
        assert response.json()["total"] == 1
    finally:
        set_container(original_container)


@pytest.mark.parametrize("repository_mode", ["json", "sqlite"])
def test_internal_inbox_supports_read_state(tmp_path, monkeypatch, repository_mode):
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", repository_mode)
    if repository_mode == "sqlite":
        monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(tmp_path / "storage" / "platform.sqlite3"))
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        signal_id = _create_signal(client)
        client.post(
            "/api/notifications/rules",
            json={
                "rule_name": "Inbox digest",
                "risk_level_threshold": "medium",
                "channels": ["internal_inbox"],
                "cron_expr": "* * * * *",
            },
        )
        response = client.post(
            "/api/notifications/run-scheduled",
            json={"now": datetime.utcnow().replace(second=0, microsecond=0).isoformat()},
        )
        assert response.status_code == 200

        inbox_response = client.get("/api/notifications/inbox")
        assert inbox_response.status_code == 200
        inbox = inbox_response.json()
        assert inbox["unread_count"] == 1
        assert inbox["items"][0]["target_id"] == signal_id
        assert inbox["items"][0]["read"] is False
        assert "notification signal" in inbox["items"][0]["title"]

        delivery_id = inbox["items"][0]["id"]
        mark_response = client.patch(f"/api/notifications/inbox/{delivery_id}", json={"read": True})
        assert mark_response.status_code == 200
        assert mark_response.json()["item"]["read"] is True

        unread_response = client.get("/api/notifications/inbox", params={"unread_only": True})
        assert unread_response.status_code == 200
        assert unread_response.json()["items"] == []
        assert unread_response.json()["unread_count"] == 0

        unmark_response = client.patch(f"/api/notifications/inbox/{delivery_id}", json={"read": False})
        assert unmark_response.status_code == 200
        assert unmark_response.json()["item"]["read"] is False

        mark_all_response = client.post("/api/notifications/inbox/mark-all-read")
        assert mark_all_response.status_code == 200
        assert mark_all_response.json()["updated_count"] == 1
    finally:
        set_container(original_container)
