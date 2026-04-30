from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.api.dependencies import container as current_container, set_container
from app.application.crawler_runner import CrawlerRunResult
from app.main import app


class FakeCrawlerRunner:
    def __init__(self, root: Path):
        self.root = root

    def run(self, task, run):
        output_dir = self.root / "storage" / "fake_crawler_output" / run.id / task.platform.value / "jsonl"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{task.task_mode.value}_contents_2026-04-30.jsonl"
        output_file.write_text(
            '{"note_id":"n1","title":"risk title","source_keyword":"春日穿搭"}\n'
            '{"note_id":"n2","title":"another title","source_keyword":"春日穿搭"}\n',
            encoding="utf-8",
        )
        log_path = self.root / "storage" / "fake_crawler_output" / f"{run.id}.log"
        log_path.write_text("line 1\nfake crawler completed\n", encoding="utf-8")
        return CrawlerRunResult(
            return_code=0,
            log_path=log_path,
            output_files=[output_file],
            redacted_command=["uv", "run", "python", "main.py", "--platform", task.platform.value],
        )


def test_platform_models_expose_xianyu():
    client = TestClient(app)
    response = client.get("/api/platforms")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["platform"] == "xianyu" for item in payload)
    xianyu = next(item for item in payload if item["platform"] == "xianyu")
    assert "seller_template_reuse" in xianyu["supported_signal_extractors"]
    assert "seller_risk_profile" in xianyu["supported_analysis_types"]


def test_task_crud_flow(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        create_payload = {
            "task_name": "XHS Seed Task",
            "platform": "xhs",
            "entity_type": "content",
            "task_mode": "search",
            "scenario_type": "lead_diversion",
            "task_payload_json": {"keywords": ["春日穿搭"]},
            "filter_payload_json": {"start_page": 1},
            "runtime_payload_json": {"enable_comments": True},
            "storage_profile_json": {"save_option": "jsonl"},
            "analysis_profile_json": {"analysis_types": ["content_structure"]},
            "notes": "task from test",
        }

        create_response = client.post("/api/tasks", json=create_payload)
        assert create_response.status_code == 200
        task = create_response.json()["task"]
        assert task["task_name"] == "XHS Seed Task"
        assert task["scenario_type"] == "lead_diversion"

        list_response = client.get("/api/tasks")
        assert list_response.status_code == 200
        assert len(list_response.json()["tasks"]) == 1

        run_response = client.post(f"/api/tasks/{task['id']}/runs")
        assert run_response.status_code == 200
        run = run_response.json()["run"]
        assert run["task_id"] == task["id"]
        assert run["status"] == "succeeded"
        assert run["task_snapshot_json"]["scenario_type"] == "lead_diversion"
        assert len(run["result_dataset_ids"]) == 1

        runs_response = client.get(f"/api/tasks/{task['id']}/runs")
        assert runs_response.status_code == 200
        assert runs_response.json()["runs"][0]["id"] == run["id"]

        dataset_response = client.get(f"/api/datasets/{run['result_dataset_id']}/preview")
        assert dataset_response.status_code == 200
        assert dataset_response.json()["total"] == 2

        logs_response = client.get("/api/logs/runs")
        assert logs_response.status_code == 200
        assert logs_response.json()["logs"][0]["has_log"] is True

        log_response = client.get(f"/api/logs/runs/{run['id']}")
        assert log_response.status_code == 200
        assert "fake crawler completed" in log_response.json()["content"]

        update_response = client.patch(
            f"/api/tasks/{task['id']}",
            json={"notes": "updated note", "status": "disabled"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["task"]["notes"] == "updated note"

        delete_response = client.delete(f"/api/tasks/{task['id']}")
        assert delete_response.status_code == 200
    finally:
        set_container(original_container)


def test_disabled_task_cannot_start_from_cron(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/tasks",
            json={
                "task_name": "Disabled Cron Task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "status": "disabled",
                "task_payload_json": {"keywords": ["导流"]},
            },
        )
        assert create_response.status_code == 200
        task = create_response.json()["task"]

        run_response = client.post(
            f"/api/tasks/{task['id']}/runs",
            json={"trigger_type": "cron", "execute_crawler": False},
        )
        assert run_response.status_code == 400
        assert "Disabled task" in run_response.json()["detail"]
    finally:
        set_container(original_container)
