from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
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
