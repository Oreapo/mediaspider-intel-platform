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


def _create_dataset(client: TestClient) -> str:
    response = client.post(
        "/api/datasets",
        json={
            "dataset_name": "Entity Source Dataset",
            "dataset_type": "raw",
            "source_platform": "xhs",
            "scenario_type": "lead_diversion",
        },
    )
    assert response.status_code == 200
    return response.json()["dataset"]["id"]


def _create_signal(client: TestClient, dataset_id: str, contact_point: str, status: str = "confirmed") -> str:
    response = client.post(
        "/api/signals",
        json={
            "dataset_id": dataset_id,
            "signal_type": "contact_point_hit",
            "signal_source": "rule:contact_points",
            "risk_level": "high",
            "risk_score": 85,
            "summary": f"疑似联系方式或导流点：{contact_point}",
            "status": status,
            "payload_json": {
                "contact_point": contact_point,
                "source_ref": {
                    "dataset_id": dataset_id,
                    "row_index": 0,
                    "source_entity_id": "note_001",
                    "raw_ref": "https://example.test/note_001",
                },
            },
        },
    )
    assert response.status_code == 200
    return response.json()["signal"]["id"]


def test_entity_can_be_created_from_confirmed_signal_with_detail(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_id = _create_dataset(client)
        signal_id = _create_signal(client, dataset_id, "abc12345")

        create_response = client.post(
            "/api/entities/from-signal",
            json={"signal_id": signal_id},
        )
        assert create_response.status_code == 200
        entity = create_response.json()["entity"]
        assert entity["entity_type"] == "contact_point"
        assert entity["display_name"] == "abc12345"
        assert entity["platform"] == "xhs"
        assert entity["profile_json"]["linked_signal_ids"] == [signal_id]

        detail_response = client.get(f"/api/entities/{entity['id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["entity"]["id"] == entity["id"]
        assert detail["signals"][0]["id"] == signal_id
        assert detail["datasets"][0]["id"] == dataset_id
        assert detail["cases"] == []
    finally:
        set_container(original_container)


def test_entity_from_unconfirmed_signal_returns_400(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_id = _create_dataset(client)
        signal_id = _create_signal(client, dataset_id, "abc12345", status="new")

        response = client.post(
            "/api/entities/from-signal",
            json={"signal_id": signal_id},
        )
        assert response.status_code == 400
    finally:
        set_container(original_container)


def test_entity_duplicate_alias_merges_linked_signals(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        dataset_id = _create_dataset(client)
        first_signal_id = _create_signal(client, dataset_id, "abc12345")
        second_signal_id = _create_signal(client, dataset_id, "abc12345")

        first_response = client.post("/api/entities/from-signal", json={"signal_id": first_signal_id})
        second_response = client.post("/api/entities/from-signal", json={"signal_id": second_signal_id})

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        first_entity = first_response.json()["entity"]
        second_entity = second_response.json()["entity"]
        assert first_entity["id"] == second_entity["id"]
        assert second_entity["profile_json"]["linked_signal_ids"] == [first_signal_id, second_signal_id]

        list_response = client.get("/api/entities")
        assert list_response.status_code == 200
        assert len(list_response.json()["entities"]) == 1
    finally:
        set_container(original_container)


def test_entity_list_supports_filters_search_and_pagination(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        samples = [
            {
                "entity_type": "account",
                "display_name": "risk_account",
                "platform": "xhs",
                "risk_score": 72,
                "status": "active",
                "source_ref": {"source_entity_id": "account_001"},
                "profile_json": {"aliases": ["risk_account", "ra001"]},
            },
            {
                "entity_type": "contact_point",
                "display_name": "abc12345",
                "platform": "xhs",
                "risk_score": 88,
                "status": "active",
                "source_ref": {"contact_point": "abc12345"},
                "profile_json": {"aliases": ["abc12345"]},
            },
            {
                "entity_type": "seller",
                "display_name": "seller_1",
                "platform": "xianyu",
                "risk_score": 45,
                "status": "dismissed",
                "source_ref": {"seller_id": "seller_1"},
                "profile_json": {"aliases": ["seller_1"]},
            },
        ]
        for item in samples:
            response = client.post("/api/entities", json=item)
            assert response.status_code == 200

        platform_response = client.get("/api/entities", params={"platform": "xianyu"})
        assert platform_response.status_code == 200
        assert platform_response.json()["entities"][0]["display_name"] == "seller_1"

        type_response = client.get("/api/entities", params={"entity_type": "contact_point"})
        assert type_response.status_code == 200
        assert type_response.json()["entities"][0]["risk_score"] == 88

        status_response = client.get("/api/entities", params={"status": "dismissed"})
        assert status_response.status_code == 200
        assert status_response.json()["entities"][0]["platform"] == "xianyu"

        risk_response = client.get("/api/entities", params={"min_risk_score": 80})
        assert risk_response.status_code == 200
        assert [item["display_name"] for item in risk_response.json()["entities"]] == ["abc12345"]

        query_response = client.get("/api/entities", params={"q": "ra001"})
        assert query_response.status_code == 200
        assert query_response.json()["entities"][0]["display_name"] == "risk_account"

        page_response = client.get("/api/entities", params={"limit": 1, "offset": 1})
        assert page_response.status_code == 200
        assert len(page_response.json()["entities"]) == 1
        assert page_response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_relation_duplicate_is_merged_with_evidence(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        account_response = client.post(
            "/api/entities",
            json={
                "entity_type": "account",
                "display_name": "risk_account",
                "platform": "xhs",
                "risk_score": 70,
                "source_ref": {"source_entity_id": "account_001"},
                "profile_json": {"aliases": ["risk_account"]},
            },
        )
        contact_response = client.post(
            "/api/entities",
            json={
                "entity_type": "contact_point",
                "display_name": "abc12345",
                "platform": "xhs",
                "risk_score": 85,
                "source_ref": {"contact_point": "abc12345"},
                "profile_json": {"aliases": ["abc12345"]},
            },
        )
        source_id = account_response.json()["entity"]["id"]
        target_id = contact_response.json()["entity"]["id"]

        first_response = client.post(
            "/api/entities/relations",
            json={
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "relation_type": "uses_contact_point",
                "confidence": 0.7,
                "evidence_ref_json": {"signal_id": "sig_001"},
            },
        )
        second_response = client.post(
            "/api/entities/relations",
            json={
                "source_entity_id": target_id,
                "target_entity_id": source_id,
                "relation_type": "uses_contact_point",
                "confidence": 0.9,
                "evidence_ref_json": {"signal_id": "sig_002"},
            },
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        first_relation = first_response.json()["relation"]
        second_relation = second_response.json()["relation"]
        assert first_relation["id"] == second_relation["id"]
        assert second_relation["confidence"] == 0.9
        assert second_relation["evidence_ref_json"]["signal_id"] == ["sig_001", "sig_002"]

        list_response = client.get("/api/entities/relations")
        assert len(list_response.json()["relations"]) == 1
    finally:
        set_container(original_container)
