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


def _create_dataset(client: TestClient, tmp_path: Path) -> str:
    dataset_file_dir = tmp_path / "storage" / "dataset_files"
    dataset_file_dir.mkdir(parents=True, exist_ok=True)
    sample_path = dataset_file_dir / "case_source.jsonl"
    sample_path.write_text(
        json.dumps({"content_id": "note_case_001", "body": "微信 abc12345 引流"}, ensure_ascii=False),
        encoding="utf-8",
    )
    response = client.post(
        "/api/datasets",
        json={
            "dataset_name": "Case Source Dataset",
            "dataset_type": "raw",
            "source_platform": "xhs",
            "scenario_type": "lead_diversion",
            "storage_uri": "case_source.jsonl",
        },
    )
    assert response.status_code == 200
    return response.json()["dataset"]["id"]


def _create_signal(client: TestClient, dataset_id: str) -> str:
    response = client.post(
        "/api/signals",
        json={
            "dataset_id": dataset_id,
            "signal_type": "contact_point_hit",
            "signal_source": "rule:contact_points",
            "risk_level": "high",
            "risk_score": 85,
            "summary": "疑似联系方式或导流点：abc12345",
            "status": "confirmed",
            "payload_json": {
                "contact_point": "abc12345",
                "source_ref": {
                    "dataset_id": dataset_id,
                    "row_index": 0,
                    "source_entity_id": "note_case_001",
                },
            },
        },
    )
    assert response.status_code == 200
    return response.json()["signal"]["id"]


def _create_entity(client: TestClient, signal_id: str) -> str:
    response = client.post("/api/entities/from-signal", json={"signal_id": signal_id})
    assert response.status_code == 200
    return response.json()["entity"]["id"]


def _create_analysis_output(client: TestClient, dataset_id: str) -> str:
    job_response = client.post(
        "/api/analysis/jobs",
        json={
            "dataset_id": dataset_id,
            "analysis_scope": "common",
            "analysis_type": "case_summary",
            "parameters_json": {},
        },
    )
    assert job_response.status_code == 200
    job_id = job_response.json()["job"]["id"]
    outputs_response = client.get(f"/api/analysis/jobs/{job_id}/outputs")
    assert outputs_response.status_code == 200
    return outputs_response.json()["outputs"][0]["id"]


def test_case_can_attach_objects_add_note_and_build_timeline(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_id = _create_dataset(client, tmp_path)
        signal_id = _create_signal(client, dataset_id)
        entity_id = _create_entity(client, signal_id)
        output_id = _create_analysis_output(client, dataset_id)

        case_response = client.post(
            "/api/cases",
            json={
                "case_name": "导流链路专项",
                "case_type": "lead_diversion",
                "priority": "high",
                "summary": "围绕联系方式 abc12345 的初始案件",
                "owner": "analyst",
            },
        )
        assert case_response.status_code == 200
        case_id = case_response.json()["case"]["id"]

        for link_type, target_id in [
            ("dataset", dataset_id),
            ("signal", signal_id),
            ("entity", entity_id),
            ("analysis_output", output_id),
        ]:
            link_response = client.post(
                f"/api/cases/{case_id}/links",
                json={
                    "link_type": link_type,
                    "target_id": target_id,
                    "label": f"{link_type}:{target_id}",
                    "source_ref_json": {"reason": "test_attach"},
                },
            )
            assert link_response.status_code == 200

        note_response = client.post(
            f"/api/cases/{case_id}/notes",
            json={"author": "analyst", "body": "已确认联系方式与内容记录有关联。"},
        )
        assert note_response.status_code == 200

        detail_response = client.get(f"/api/cases/{case_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["case"]["case_name"] == "导流链路专项"
        assert len(detail["links"]) == 4
        assert len(detail["notes"]) == 1
        assert detail["objects"]["datasets"][0]["id"] == dataset_id
        assert detail["objects"]["signals"][0]["id"] == signal_id
        assert detail["objects"]["entities"][0]["id"] == entity_id
        assert detail["objects"]["analysis_outputs"][0]["id"] == output_id
        assert {event["action"] for event in detail["audit_events"]} >= {"case.create", "case.link.add", "case.note.add"}
        assert all(event["target_type"] == "case" for event in detail["audit_events"])

        timeline_response = client.get(f"/api/cases/{case_id}/timeline")
        assert timeline_response.status_code == 200
        timeline = timeline_response.json()["timeline"]
        event_types = [item["event_type"] for item in timeline]
        assert "case_created" in event_types
        assert "dataset_attached" in event_types
        assert "signal_attached" in event_types
        assert "entity_attached" in event_types
        assert "analysis_output_attached" in event_types
        assert "note_added" in event_types
        assert all("source_ref" in item for item in timeline)
    finally:
        set_container(original_container)


def test_case_duplicate_link_is_merged(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_id = _create_dataset(client, tmp_path)
        case_id = client.post(
            "/api/cases",
            json={"case_name": "重复挂接测试", "case_type": "lead_diversion"},
        ).json()["case"]["id"]

        first = client.post(
            f"/api/cases/{case_id}/links",
            json={"link_type": "dataset", "target_id": dataset_id, "source_ref_json": {"a": 1}},
        )
        second = client.post(
            f"/api/cases/{case_id}/links",
            json={"link_type": "dataset", "target_id": dataset_id, "label": "merged", "source_ref_json": {"b": 2}},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["link"]["id"] == second.json()["link"]["id"]
        assert second.json()["link"]["source_ref_json"] == {"a": 1, "b": 2}

        detail = client.get(f"/api/cases/{case_id}").json()
        assert len(detail["links"]) == 1
    finally:
        set_container(original_container)


def test_case_list_supports_filters_search_and_pagination(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        samples = [
            {
                "case_name": "小红书导流链路专项",
                "case_type": "lead_diversion",
                "status": "investigating",
                "priority": "high",
                "summary": "围绕联系方式 abc12345 的调查",
                "owner": "alice",
            },
            {
                "case_name": "闲鱼商品异常价格专项",
                "case_type": "product_risk",
                "status": "open",
                "priority": "medium",
                "summary": "低价商品和模板复用排查",
                "owner": "bob",
            },
            {
                "case_name": "微博话题扩散复核",
                "case_type": "topic_watch",
                "status": "closed",
                "priority": "low",
                "summary": "同话术传播簇已复核",
                "owner": "alice",
            },
        ]
        for item in samples:
            response = client.post("/api/cases", json=item)
            assert response.status_code == 200

        high_response = client.get("/api/cases", params={"priority": "high"})
        assert high_response.status_code == 200
        assert [item["case_name"] for item in high_response.json()["cases"]] == ["小红书导流链路专项"]

        owner_response = client.get("/api/cases", params={"owner": "ali"})
        assert owner_response.status_code == 200
        assert len(owner_response.json()["cases"]) == 2

        query_response = client.get("/api/cases", params={"q": "abc12345"})
        assert query_response.status_code == 200
        assert query_response.json()["cases"][0]["case_type"] == "lead_diversion"

        type_response = client.get("/api/cases", params={"case_type": "product_risk", "status": "open"})
        assert type_response.status_code == 200
        assert type_response.json()["cases"][0]["owner"] == "bob"

        page_response = client.get("/api/cases", params={"limit": 1, "offset": 1})
        assert page_response.status_code == 200
        assert len(page_response.json()["cases"]) == 1
        assert page_response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_case_link_missing_target_returns_404(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        case_id = client.post(
            "/api/cases",
            json={"case_name": "缺失对象测试", "case_type": "lead_diversion"},
        ).json()["case"]["id"]

        response = client.post(
            f"/api/cases/{case_id}/links",
            json={"link_type": "signal", "target_id": "sig_missing"},
        )
        assert response.status_code == 404
    finally:
        set_container(original_container)
