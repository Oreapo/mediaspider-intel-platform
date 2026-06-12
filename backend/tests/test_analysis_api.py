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


def test_analysis_job_generates_outputs(tmp_path):
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        dataset_file_dir = tmp_path / "storage" / "dataset_files"
        dataset_file_dir.mkdir(parents=True, exist_ok=True)
        sample_path = dataset_file_dir / "wb_posts.jsonl"
        sample_path.write_text(
            "\n".join(
                [
                    json.dumps({"title": "新品发布", "content": "品牌上新发布会", "tag": "品牌"}, ensure_ascii=False),
                    json.dumps({"title": "活动预热", "content": "活动预热情报", "tag": "活动"}, ensure_ascii=False),
                ]
            ),
            encoding="utf-8",
        )

        client = TestClient(app)
        dataset_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "Weibo Posts",
                "dataset_type": "raw",
                "source_platform": "wb",
                "storage_uri": "wb_posts.jsonl",
            },
        )
        dataset_id = dataset_response.json()["dataset"]["id"]

        create_job_response = client.post(
            "/api/analysis/jobs",
            json={
                "dataset_id": dataset_id,
                "analysis_scope": "common",
                "analysis_type": "keyword_heatmap",
                "parameters_json": {"language": "zh-CN"},
            },
        )
        assert create_job_response.status_code == 200
        job = create_job_response.json()["job"]
        assert job["status"] == "succeeded"

        outputs_response = client.get(f"/api/analysis/jobs/{job['id']}/outputs")
        assert outputs_response.status_code == 200
        outputs = outputs_response.json()["outputs"]
        assert len(outputs) == 1
        assert outputs[0]["payload_json"]["dataset_name"] == "Weibo Posts"
        assert outputs[0]["payload_json"]["analysis_type"] == "keyword_heatmap"

        second_job = client.post(
            "/api/analysis/jobs",
            json={
                "dataset_id": dataset_id,
                "analysis_scope": "common",
                "analysis_type": "summary",
                "parameters_json": {},
            },
        ).json()["job"]
        first_page = client.get("/api/analysis/jobs", params={"limit": 1, "offset": 0})
        second_page = client.get("/api/analysis/jobs", params={"limit": 1, "offset": 1})
        assert first_page.status_code == 200
        assert first_page.json()["total"] == 2
        assert second_page.status_code == 200
        assert second_page.json()["total"] == 2
        assert {
            first_page.json()["jobs"][0]["id"],
            second_page.json()["jobs"][0]["id"],
        } == {job["id"], second_job["id"]}
    finally:
        set_container(original_container)
