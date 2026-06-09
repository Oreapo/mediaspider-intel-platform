from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
from app.main import app


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "analyst", "password": "secret"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _create_case_with_signal(client: TestClient, tmp_path: Path, headers: dict[str, str] | None = None) -> str:
    dataset_file_dir = tmp_path / "storage" / "dataset_files"
    dataset_file_dir.mkdir(parents=True, exist_ok=True)
    (dataset_file_dir / "evidence_source.jsonl").write_text(
        json.dumps({"content_id": "note_evidence_001", "body": "微信 abc12345 引流"}, ensure_ascii=False),
        encoding="utf-8",
    )
    dataset = client.post(
        "/api/datasets",
        json={
            "dataset_name": "Evidence Source Dataset",
            "dataset_type": "raw",
            "source_platform": "xhs",
            "scenario_type": "lead_diversion",
            "storage_uri": "evidence_source.jsonl",
        },
        headers=headers,
    ).json()["dataset"]
    signal = client.post(
        "/api/signals",
        json={
            "dataset_id": dataset["id"],
            "signal_type": "contact_point_hit",
            "signal_source": "rule:contact_points",
            "risk_level": "high",
            "risk_score": 85,
            "summary": "疑似联系方式或导流点：abc12345",
            "status": "confirmed",
            "payload_json": {
                "contact_point": "abc12345",
                "source_ref": {
                    "dataset_id": dataset["id"],
                    "row_index": 0,
                    "source_entity_id": "note_evidence_001",
                },
            },
        },
        headers=headers,
    ).json()["signal"]
    case = client.post(
        "/api/cases",
        json={
            "case_name": "证据包专项",
            "case_type": "lead_diversion",
            "priority": "high",
            "summary": "用于证据包测试的案件",
        },
        headers=headers,
    ).json()["case"]
    for link_type, target_id in [("dataset", dataset["id"]), ("signal", signal["id"])]:
        response = client.post(
            f"/api/cases/{case['id']}/links",
            json={"link_type": link_type, "target_id": target_id},
            headers=headers,
        )
        assert response.status_code == 200
    note_response = client.post(
        f"/api/cases/{case['id']}/notes",
        json={"author": "analyst", "body": "证据链条初步完整。"},
        headers=headers,
    )
    assert note_response.status_code == 200
    return case["id"]


def test_evidence_packet_generation_persists_manifest_and_links_case(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        case_id = _create_case_with_signal(client, tmp_path)

        response = client.post(
            "/api/evidence/packets",
            json={"case_id": case_id, "packet_name": "导流链路证据包"},
        )
        assert response.status_code == 200
        packet = response.json()["packet"]
        assert packet["case_id"] == case_id
        assert packet["storage_uri"].endswith(".json")
        assert packet["manifest_json"]["case"]["id"] == case_id
        assert packet["manifest_json"]["summary"]["signal_count"] == 1
        assert packet["manifest_json"]["source_records"]

        artifact_path = tmp_path / "storage" / "evidence_packet_files" / packet["storage_uri"]
        assert artifact_path.exists()
        manifest = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert manifest["packet_id"] == packet["id"]

        detail = client.get(f"/api/cases/{case_id}").json()
        evidence_links = [link for link in detail["links"] if link["link_type"] == "evidence_packet"]
        assert len(evidence_links) == 1
        assert detail["objects"]["evidence_packets"][0]["id"] == packet["id"]
    finally:
        set_container(original_container)


def test_evidence_packet_download_returns_artifact(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        case_id = _create_case_with_signal(client, tmp_path)
        packet = client.post(
            "/api/evidence/packets",
            json={"case_id": case_id, "packet_name": "download_packet"},
        ).json()["packet"]

        response = client.get(f"/api/evidence/{packet['id']}/download")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        payload = response.json()
        assert payload["packet_id"] == packet["id"]
        assert payload["case"]["id"] == case_id
    finally:
        set_container(original_container)


def test_evidence_packet_download_accepts_query_access_token_when_auth_required(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", "analyst:secret:analyst:Risk Analyst")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        headers = _auth_headers(client)
        case_id = _create_case_with_signal(client, tmp_path, headers=headers)
        packet = client.post(
            "/api/evidence/packets",
            json={"case_id": case_id, "packet_name": "query_token_packet"},
            headers=headers,
        ).json()["packet"]
        token = headers["Authorization"].split(" ", 1)[1]

        response = client.get(f"/api/evidence/{packet['id']}/download", params={"access_token": token})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["packet_id"] == packet["id"]
    finally:
        set_container(original_container)


def test_evidence_packet_missing_case_returns_404(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/evidence/packets",
            json={"case_id": "case_missing", "packet_name": "missing"},
        )
        assert response.status_code == 404
    finally:
        set_container(original_container)
