from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import container as current_container, set_container
from app.api.dependencies.container import AppContainer
from app.application.crawler_runner import CrawlerRunResult
from app.main import app


class InspectingCrawlerRunner:
    def __init__(self):
        self.last_runtime_payload = {}

    def run(self, task, run):
        self.last_runtime_payload = dict(task.runtime_payload_json)
        return CrawlerRunResult(
            return_code=0,
            log_path=Path(run.id + ".log"),
            output_files=[],
            redacted_command=["python", "main.py", "--cookies", "<redacted>"],
        )

    def diagnose(self, task):
        self.last_runtime_payload = dict(task.runtime_payload_json)
        return {
            "ready": True,
            "errors": [],
            "warnings": [],
            "command": ["python", "main.py", "--cookies", "<redacted>"],
            "raw_command": [],
        }


def test_platform_profile_crud_and_diagnostics(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=InspectingCrawlerRunner())
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/platforms/profiles",
            json={
                "platform": "xhs",
                "profile_name": "XHS Production Cookie",
                "auth_type": "cookie",
                "credentials_ref": "secret-cookie-value",
                "settings_json": {"headless": True},
            },
        )
        assert create_response.status_code == 200
        profile = create_response.json()["profile"]
        assert profile["profile_name"] == "XHS Production Cookie"
        assert profile["credentials_ref"] != "secret-cookie-value"

        list_response = client.get("/api/platforms/profiles", params={"platform": "xhs"})
        assert list_response.status_code == 200
        assert list_response.json()["profiles"][0]["id"] == profile["id"]

        diagnostics_response = client.get(f"/api/platforms/profiles/{profile['id']}/diagnostics")
        assert diagnostics_response.status_code == 200
        diagnostics = diagnostics_response.json()["diagnostics"]
        assert diagnostics["ready"] is True
        assert "cookies" in diagnostics["runtime_keys"]

        update_response = client.patch(
            f"/api/platforms/profiles/{profile['id']}",
            json={"profile_name": "XHS Cookie Updated"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["profile"]["profile_name"] == "XHS Cookie Updated"

        delete_response = client.delete(f"/api/platforms/profiles/{profile['id']}")
        assert delete_response.status_code == 200
        assert client.get(f"/api/platforms/profiles/{profile['id']}").status_code == 404
    finally:
        set_container(original_container)


def test_task_run_applies_platform_auth_profile(tmp_path):
    runner = InspectingCrawlerRunner()
    test_container = AppContainer(tmp_path, crawler_runner=runner)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        profile = client.post(
            "/api/platforms/profiles",
            json={
                "platform": "xhs",
                "profile_name": "XHS Runtime Cookie",
                "auth_type": "cookie",
                "credentials_ref": "cookie-from-profile",
                "settings_json": {"headless": True, "max_concurrency_num": 3},
            },
        ).json()["profile"]
        task = client.post(
            "/api/tasks",
            json={
                "task_name": "Profile Runtime Task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "auth_profile_id": profile["id"],
                "task_payload_json": {"keywords": ["导流"]},
                "runtime_payload_json": {"enable_comments": False},
            },
        ).json()["task"]

        diagnostics_response = client.get(f"/api/tasks/{task['id']}/crawler-diagnostics")
        assert diagnostics_response.status_code == 200
        assert runner.last_runtime_payload["cookies"] == "cookie-from-profile"
        assert runner.last_runtime_payload["headless"] is True

        run_response = client.post(f"/api/tasks/{task['id']}/runs")
        assert run_response.status_code == 202
        submitted = run_response.json()["run"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            run = client.get(
                f"/api/tasks/{task['id']}/runs/{submitted['id']}"
            ).json()["run"]
            if run["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.01)
        else:
            raise AssertionError(f"Task run did not finish: {submitted['id']}")
        assert run["status"] == "succeeded"
        assert run["task_snapshot_json"]["runtime_payload_json"]["auth_profile_id"] == profile["id"]
        assert runner.last_runtime_payload["max_concurrency_num"] == 3
    finally:
        set_container(original_container)
