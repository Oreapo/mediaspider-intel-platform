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


def test_dataset_crud_and_preview(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "xhs_notes.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    json.dumps({"title": "春日穿搭", "tag": "通勤"}, ensure_ascii=False),
                    json.dumps({"title": "轻户外穿搭", "tag": "徒步"}, ensure_ascii=False),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        create_payload = {
            "dataset_name": "XHS Notes",
            "dataset_type": "raw",
            "source_platform": "xhs",
            "scenario_type": "lead_diversion",
            "storage_uri": "xhs_notes.jsonl",
            "tags": ["fashion", "spring"],
        }

        create_response = client.post("/api/datasets", json=create_payload)
        assert create_response.status_code == 200
        dataset = create_response.json()["dataset"]
        assert dataset["record_count"] == 2
        assert dataset["scenario_type"] == "lead_diversion"

        list_response = client.get("/api/datasets")
        assert list_response.status_code == 200
        assert len(list_response.json()["datasets"]) == 1

        preview_response = client.get(f"/api/datasets/{dataset['id']}/preview")
        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        assert "title" in preview_payload["columns"]
        assert len(preview_payload["rows"]) == 2

        delete_response = client.delete(f"/api/datasets/{dataset['id']}")
        assert delete_response.status_code == 200
    finally:
        set_container(original_container)


def test_jsonl_preview_limits_records_not_physical_lines(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "sparse_notes.jsonl"
        sample_path.write_text(
            "\n"
            + json.dumps({"title": "first"}, ensure_ascii=False)
            + "\n\n"
            + json.dumps({"title": "second"}, ensure_ascii=False)
            + "\n"
            + json.dumps({"title": "third"}, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )

        client = TestClient(app)
        create_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Sparse Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "storage_uri": "sparse_notes.jsonl",
            },
        )
        assert create_response.status_code == 200
        dataset = create_response.json()["dataset"]
        assert dataset["record_count"] == 3

        preview_response = client.get(f"/api/datasets/{dataset['id']}/preview", params={"limit": 2})

        assert preview_response.status_code == 200
        preview = preview_response.json()
        assert preview["rows"] == [["first"], ["second"]]
    finally:
        set_container(original_container)


def test_dataset_list_supports_filters_search_and_pagination(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        samples = [
            {
                "dataset_name": "XHS Lead Notes",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "scenario_type": "lead_diversion",
                "storage_uri": "xhs_leads.jsonl",
                "tags": ["lead", "spring"],
            },
            {
                "dataset_name": "DY Topic Videos",
                "dataset_type": "analysis_ready",
                "source_platform": "dy",
                "scenario_type": "topic_watch",
                "storage_uri": "dy_topics.jsonl",
                "tags": ["topic", "video"],
            },
            {
                "dataset_name": "Xianyu Product Risk",
                "dataset_type": "normalized",
                "source_platform": "xianyu",
                "scenario_type": "product_risk",
                "storage_uri": "xianyu_products.jsonl",
                "tags": ["seller", "price"],
            },
        ]
        for item in samples:
            response = client.post("/api/datasets", json=item)
            assert response.status_code == 200

        platform_response = client.get("/api/datasets", params={"source_platform": "xhs"})
        assert platform_response.status_code == 200
        assert [item["dataset_name"] for item in platform_response.json()["datasets"]] == ["XHS Lead Notes"]

        scenario_response = client.get("/api/datasets", params={"scenario_type": "topic_watch"})
        assert scenario_response.status_code == 200
        assert scenario_response.json()["datasets"][0]["source_platform"] == "dy"

        tag_response = client.get("/api/datasets", params={"tag": "price"})
        assert tag_response.status_code == 200
        assert tag_response.json()["datasets"][0]["dataset_name"] == "Xianyu Product Risk"

        query_response = client.get("/api/datasets", params={"q": "dy_topics"})
        assert query_response.status_code == 200
        assert query_response.json()["datasets"][0]["scenario_type"] == "topic_watch"

        page_response = client.get("/api/datasets", params={"limit": 1, "offset": 1})
        assert page_response.status_code == 200
        assert len(page_response.json()["datasets"]) == 1
        assert page_response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_dataset_list_contract_is_preserved_in_sqlite_mode(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        for index in range(3):
            response = client.post(
                "/api/datasets",
                json={
                    "dataset_name": f"SQLite Lead Dataset {index}",
                    "dataset_type": "raw",
                    "source_platform": "xhs",
                    "scenario_type": "lead_diversion",
                    "storage_uri": f"sqlite_lead_{index}.jsonl",
                    "tags": ["lead", f"batch-{index}"],
                },
            )
            assert response.status_code == 200

        response = client.get(
            "/api/datasets",
            params={
                "source_platform": "xhs",
                "tag": "lead",
                "q": "sqlite_lead",
                "limit": 1,
                "offset": 1,
            },
        )

        assert response.status_code == 200
        assert set(response.json()) == {"datasets", "total"}
        assert len(response.json()["datasets"]) == 1
        assert response.json()["total"] == 3
    finally:
        set_container(original_container)
