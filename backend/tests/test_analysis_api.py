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
from app.domain.models.analysis import AnalysisJob, AnalysisOutput, AnalysisScope
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

        batch_outputs = client.get(
            "/api/analysis/outputs",
            params=[("job_ids", job["id"]), ("job_ids", second_job["id"])],
        )
        assert batch_outputs.status_code == 200
        assert {
            output["analysis_job_id"] for output in batch_outputs.json()["outputs"]
        } == {job["id"], second_job["id"]}
    finally:
        set_container(original_container)


def test_analysis_job_list_filters_by_dataset_in_sqlite_mode(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))
    test_container = AppContainer(tmp_path)
    for job in (
        AnalysisJob(
            id="aj_first",
            dataset_id="ds_target",
            analysis_scope=AnalysisScope.COMMON,
            analysis_type="summary",
        ),
        AnalysisJob(
            id="aj_other",
            dataset_id="ds_other",
            analysis_scope=AnalysisScope.PLATFORM,
            analysis_type="topic_map",
        ),
        AnalysisJob(
            id="aj_second",
            dataset_id="ds_target",
            analysis_scope=AnalysisScope.CROSS_PLATFORM,
            analysis_type="network",
        ),
    ):
        test_container.analysis_service.repository.save_job(job)
    test_container.analysis_service.repository.save_output(
        AnalysisOutput(
            id="ao_target",
            analysis_job_id="aj_first",
            output_type="summary",
            title="Target output",
        )
    )
    test_container.analysis_service.repository.save_output(
        AnalysisOutput(
            id="ao_other",
            analysis_job_id="aj_other",
            output_type="summary",
            title="Other output",
        )
    )

    original_container = current_container
    set_container(test_container)
    try:
        response = TestClient(app).get(
            "/api/analysis/jobs",
            params={"dataset_id": "ds_target", "limit": 1, "offset": 1},
        )

        assert response.status_code == 200
        assert set(response.json()) == {"jobs", "total"}
        assert len(response.json()["jobs"]) == 1
        assert response.json()["jobs"][0]["dataset_id"] == "ds_target"
        assert response.json()["total"] == 2

        outputs_response = TestClient(app).get(
            "/api/analysis/outputs",
            params=[("job_ids", "aj_first"), ("job_ids", "aj_second")],
        )
        assert outputs_response.status_code == 200
        assert [output["id"] for output in outputs_response.json()["outputs"]] == ["ao_target"]
    finally:
        set_container(original_container)
