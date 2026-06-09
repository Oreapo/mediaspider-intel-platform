from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
from app.main import app


def test_task_mutations_write_audit_events(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/tasks",
            json={
                "task_name": "Audited Task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "task_payload_json": {"keywords": ["导流"]},
            },
        )
        assert create_response.status_code == 200
        task = create_response.json()["task"]

        update_response = client.patch(f"/api/tasks/{task['id']}", json={"notes": "changed"})
        assert update_response.status_code == 200

        audit_response = client.get("/api/logs/audit", params={"target_type": "task", "target_id": task["id"]})
        assert audit_response.status_code == 200
        events = audit_response.json()["events"]
        assert [event["action"] for event in events] == ["task.update", "task.create"]
        assert events[0]["actor_username"] == "anonymous"
        assert events[0]["metadata_json"]["fields"] == ["notes"]

        query_response = client.get("/api/logs/audit", params={"q": "notes"})
        assert query_response.status_code == 200
        assert query_response.json()["events"][0]["action"] == "task.update"

        action_response = client.get("/api/logs/audit", params={"action": "task.create"})
        assert action_response.status_code == 200
        assert [event["action"] for event in action_response.json()["events"]] == ["task.create"]

        actor_response = client.get("/api/logs/audit", params={"actor_username": "anonymous"})
        assert actor_response.status_code == 200
        assert len(actor_response.json()["events"]) == 2
    finally:
        set_container(original_container)


def test_case_evidence_and_report_actions_write_audit_events(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        case_response = client.post(
            "/api/cases",
            json={
                "case_name": "Audited Case",
                "case_type": "lead_diversion",
                "priority": "high",
                "summary": "case audit flow",
            },
        )
        assert case_response.status_code == 200
        case_id = case_response.json()["case"]["id"]

        note_response = client.post(
            f"/api/cases/{case_id}/notes",
            json={"author": "analyst", "body": "审计测试备注。"},
        )
        assert note_response.status_code == 200

        packet_response = client.post(
            "/api/evidence/packets",
            json={"case_id": case_id, "packet_name": "Audited Packet"},
        )
        assert packet_response.status_code == 200
        packet_id = packet_response.json()["packet"]["id"]

        packet_download = client.get(f"/api/evidence/{packet_id}/download")
        assert packet_download.status_code == 200

        report_response = client.post(
            "/api/reports",
            json={"case_id": case_id, "report_name": "Audited Report"},
        )
        assert report_response.status_code == 200
        report_id = report_response.json()["report"]["id"]

        report_update = client.patch(
            f"/api/reports/{report_id}",
            json={"status": "draft", "content_markdown": "# Audited Report\n"},
        )
        assert report_update.status_code == 200

        report_download = client.get(f"/api/reports/{report_id}/download")
        assert report_download.status_code == 200

        audit_response = client.get("/api/logs/audit")
        assert audit_response.status_code == 200
        actions = {event["action"] for event in audit_response.json()["events"]}
        assert {
            "case.create",
            "case.note.add",
            "evidence_packet.generate",
            "evidence_packet.download",
            "report.generate",
            "report.update",
            "report.download",
        }.issubset(actions)

        case_events = client.get("/api/logs/audit", params={"target_type": "case", "target_id": case_id})
        assert case_events.status_code == 200
        assert {event["action"] for event in case_events.json()["events"]} >= {"case.create", "case.note.add"}
    finally:
        set_container(original_container)
