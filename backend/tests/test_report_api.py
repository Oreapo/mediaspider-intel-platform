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


def _create_report_case(client: TestClient, tmp_path: Path, headers: dict[str, str] | None = None) -> str:
    dataset_file_dir = tmp_path / "storage" / "dataset_files"
    dataset_file_dir.mkdir(parents=True, exist_ok=True)
    sample_path = dataset_file_dir / "report_source.jsonl"
    sample_path.write_text(
        json.dumps({"content_id": "note_report_001", "body": "微信 abc12345 引流"}, ensure_ascii=False),
        encoding="utf-8",
    )
    dataset_id = client.post(
        "/api/datasets",
        json={
            "dataset_name": "Report Source Dataset",
            "dataset_type": "raw",
            "source_platform": "xhs",
            "scenario_type": "lead_diversion",
            "storage_uri": "report_source.jsonl",
        },
        headers=headers,
    ).json()["dataset"]["id"]
    signal_id = client.post(
        "/api/signals",
        json={
            "dataset_id": dataset_id,
            "signal_type": "contact_point_hit",
            "signal_source": "rule:contact_points",
            "risk_level": "high",
            "risk_score": 86,
            "summary": "疑似联系方式或导流点：abc12345",
            "status": "confirmed",
            "payload_json": {
                "source_ref": {
                    "dataset_id": dataset_id,
                    "row_index": 0,
                    "source_entity_id": "note_report_001",
                    "raw_ref": "https://example.test/note_report_001",
                }
            },
        },
        headers=headers,
    ).json()["signal"]["id"]
    case_id = client.post(
        "/api/cases",
        json={
            "case_name": "报告生成案件",
            "case_type": "lead_diversion",
            "priority": "high",
            "summary": "围绕联系方式 abc12345 的研判报告。",
            "owner": "analyst",
        },
        headers=headers,
    ).json()["case"]["id"]
    for link_type, target_id in [("dataset", dataset_id), ("signal", signal_id)]:
        response = client.post(
            f"/api/cases/{case_id}/links",
            json={"link_type": link_type, "target_id": target_id, "label": link_type},
            headers=headers,
        )
        assert response.status_code == 200
    note_response = client.post(
        f"/api/cases/{case_id}/notes",
        json={"author": "analyst", "body": "已确认 source_ref 可以回溯到原始记录。"},
        headers=headers,
    )
    assert note_response.status_code == 200
    packet_response = client.post(
        "/api/evidence/packets",
        json={"case_id": case_id, "packet_name": "报告证据包"},
        headers=headers,
    )
    assert packet_response.status_code == 200
    return case_id


def test_generate_report_from_case_and_download(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        case_id = _create_report_case(client, tmp_path)

        generate_response = client.post(
            "/api/reports",
            json={
                "case_id": case_id,
                "report_name": "导流链路研判报告",
                "report_type": "investigation_brief",
            },
        )
        assert generate_response.status_code == 200
        report = generate_response.json()["report"]
        assert report["case_id"] == case_id
        assert report["summary_json"]["signal_count"] == 1
        assert report["summary_json"]["evidence_packet_count"] == 1
        assert "Source Traceability" in report["content_markdown"]
        assert "note_report_001" in report["content_markdown"]

        list_response = client.get("/api/reports")
        assert list_response.status_code == 200
        assert list_response.json()["reports"][0]["id"] == report["id"]
        assert list_response.json()["total"] == 1

        second_report = client.post(
            "/api/reports",
            json={
                "case_id": case_id,
                "report_name": "导流链路研判报告 2",
                "report_type": "investigation_brief",
            },
        ).json()["report"]
        first_page = client.get("/api/reports", params={"limit": 1, "offset": 0})
        second_page = client.get("/api/reports", params={"limit": 1, "offset": 1})
        assert first_page.json()["total"] == 2
        assert second_page.json()["total"] == 2
        assert {
            first_page.json()["reports"][0]["id"],
            second_page.json()["reports"][0]["id"],
        } == {report["id"], second_report["id"]}

        detail_response = client.get(f"/api/reports/{report['id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["report"]["storage_uri"].endswith(".md")

        update_response = client.patch(
            f"/api/reports/{report['id']}",
            json={
                "report_name": "已编辑研判报告",
                "status": "draft",
                "content_markdown": "# 已编辑研判报告\n\n人工补充结论。",
            },
        )
        assert update_response.status_code == 200
        updated = update_response.json()["report"]
        assert updated["report_name"] == "已编辑研判报告"
        assert updated["status"] == "draft"
        assert "人工补充结论" in updated["content_markdown"]

        download_response = client.get(f"/api/reports/{report['id']}/download")
        assert download_response.status_code == 200
        assert "已编辑研判报告" in download_response.text
    finally:
        set_container(original_container)


def test_report_download_accepts_query_access_token_when_auth_required(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", "analyst:secret:analyst:Risk Analyst")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        headers = _auth_headers(client)
        case_id = _create_report_case(client, tmp_path, headers=headers)
        report = client.post(
            "/api/reports",
            json={
                "case_id": case_id,
                "report_name": "查询 Token 下载报告",
                "report_type": "investigation_brief",
            },
            headers=headers,
        ).json()["report"]
        token = headers["Authorization"].split(" ", 1)[1]

        header_response = client.get(f"/api/reports/{report['id']}/download", headers=headers)
        response = client.get(f"/api/reports/{report['id']}/download", params={"access_token": token})

        assert header_response.status_code == 200
        assert "查询 Token 下载报告" in header_response.text
        assert response.status_code == 200
        assert "查询 Token 下载报告" in response.text
    finally:
        set_container(original_container)


def test_generate_report_missing_case_returns_404(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/reports",
            json={"case_id": "case_missing", "report_name": "Missing Case Report"},
        )
        assert response.status_code == 404
    finally:
        set_container(original_container)
