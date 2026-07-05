from __future__ import annotations

import sys
import time
from pathlib import Path
from threading import Event

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
from app.application.crawler_runner import CrawlerRunResult
from app.main import app


class InspectingRunner:
    def __init__(self, root: Path):
        self.root = root
        self.last_task = None
        self.release = Event()

    def run(self, task, run):
        self.last_task = task
        self.release.wait(timeout=0.05)
        log_path = self.root / "storage" / "compat" / f"{run.id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("compat crawler completed successfully\n", encoding="utf-8")
        return CrawlerRunResult(
            return_code=0,
            log_path=log_path,
            output_files=[],
            redacted_command=["uv", "run", "python", "main.py", "--lt", task.runtime_payload_json["login_type"]],
        )


def test_crawler_compat_api_starts_task_and_exposes_status_logs(tmp_path):
    runner = InspectingRunner(tmp_path)
    test_container = AppContainer(tmp_path, crawler_runner=runner)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/crawler/start",
            json={
                "platform": "xhs",
                "login_type": "cookie",
                "crawler_type": "search",
                "keywords": "导流,兼职",
                "save_option": "jsonl",
                "cookies": "secret-cookie",
                "headless": True,
                "max_comments_count_singlenotes": 20,
                "max_concurrency_num": 2,
            },
        )

        assert response.status_code == 202
        payload = response.json()
        assert payload["task_id"].startswith("tsk_")
        assert payload["run_id"].startswith("run_")

        deadline = time.monotonic() + 2
        status_payload = {}
        while time.monotonic() < deadline:
            status_response = client.get("/api/crawler/status")
            assert status_response.status_code == 200
            status_payload = status_response.json()
            if status_payload["status"] == "idle":
                break
            time.sleep(0.01)

        assert status_payload["platform"] == "xhs"
        assert status_payload["crawler_type"] == "search"
        assert status_payload["task_id"] == payload["task_id"]
        assert status_payload["run_id"] == payload["run_id"]
        assert runner.last_task.task_payload_json["keywords"] == ["导流", "兼职"]
        assert runner.last_task.runtime_payload_json["login_type"] == "cookie"
        assert runner.last_task.runtime_payload_json["cookies"] == "secret-cookie"
        assert runner.last_task.runtime_payload_json["headless"] is True
        assert runner.last_task.runtime_payload_json["max_comments_count_singlenotes"] == 20
        assert runner.last_task.runtime_payload_json["max_concurrency_num"] == 2
        assert runner.last_task.storage_profile_json["save_option"] == "jsonl"

        logs_response = client.get("/api/crawler/logs")
        assert logs_response.status_code == 200
        assert logs_response.json()["logs"][0]["level"] == "success"
        assert "compat crawler completed" in logs_response.json()["logs"][0]["message"]

        stop_response = client.post("/api/crawler/stop")
        assert stop_response.status_code in {200, 409}
    finally:
        runner.release.set()
        set_container(original_container)


def test_crawler_compat_api_validates_required_mode_inputs(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=InspectingRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/crawler/start",
            json={
                "platform": "xhs",
                "crawler_type": "detail",
                "specified_ids": "",
            },
        )

        assert response.status_code == 400
        assert "specified_ids" in response.json()["detail"]
    finally:
        set_container(original_container)
