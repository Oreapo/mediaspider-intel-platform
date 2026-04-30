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
