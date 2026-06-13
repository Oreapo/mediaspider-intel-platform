from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Lock

import pytest
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.api.dependencies import container as current_container, set_container
from app.application.crawler_runner import CrawlerRunResult, MediaCrawlerProcessRunner
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


class FailingCrawlerRunner:
    def __init__(self, root: Path):
        self.root = root

    def run(self, task, run):
        log_path = self.root / "storage" / "fake_crawler_output" / f"{run.id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("crawler failed\n", encoding="utf-8")
        return CrawlerRunResult(
            return_code=1,
            log_path=log_path,
            output_files=[],
            error_message="simulated crawler failure",
            redacted_command=["uv", "run", "python", "main.py"],
        )


class BlockingCrawlerRunner:
    def __init__(self, root: Path):
        self.root = root
        self.started = Event()
        self.release = Event()
        self.guard = Lock()
        self.active_runs = 0
        self.max_active_runs = 0

    def run(self, task, run):
        with self.guard:
            self.active_runs += 1
            self.max_active_runs = max(self.max_active_runs, self.active_runs)
        self.started.set()
        try:
            self.release.wait(timeout=2)
            log_path = self.root / "storage" / "blocking_crawler_output" / f"{run.id}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("blocking crawler completed\n", encoding="utf-8")
            return CrawlerRunResult(
                return_code=0,
                log_path=log_path,
                output_files=[],
                redacted_command=["python", "blocking-crawler.py"],
            )
        finally:
            with self.guard:
                self.active_runs -= 1


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

        second_run_response = client.post(f"/api/tasks/{task['id']}/runs")
        assert second_run_response.status_code == 200
        second_run = second_run_response.json()["run"]

        runs_response = client.get(
            f"/api/tasks/{task['id']}/runs",
            params={"limit": 1, "offset": 1},
        )
        assert runs_response.status_code == 200
        assert set(runs_response.json()) == {"runs", "total", "status_counts"}
        assert len(runs_response.json()["runs"]) == 1
        assert runs_response.json()["total"] == 2
        assert runs_response.json()["status_counts"] == {"succeeded": 2, "failed": 0}
        assert runs_response.json()["runs"][0]["id"] == run["id"]

        run_detail_response = client.get(f"/api/tasks/{task['id']}/runs/{second_run['id']}")
        assert run_detail_response.status_code == 200
        assert run_detail_response.json()["run"]["id"] == second_run["id"]

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


def test_run_log_reads_tail_with_total_line_count(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        task = client.post(
            "/api/tasks",
            json={
                "task_name": "Tail Log Task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "task_payload_json": {"keywords": ["导流"]},
            },
        ).json()["task"]
        run = client.post(f"/api/tasks/{task['id']}/runs").json()["run"]
        Path(run["log_path"]).write_text("\n".join(f"line {index}" for index in range(1, 11)), encoding="utf-8")

        response = client.get(f"/api/logs/runs/{run['id']}", params={"max_lines": 3})

        assert response.status_code == 200
        payload = response.json()
        assert payload["line_count"] == 10
        assert payload["truncated"] is True
        assert payload["content"] == "line 8\nline 9\nline 10"
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


def test_task_list_supports_filters_search_and_pagination(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        samples = [
            {
                "task_name": "XHS Lead Search",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "status": "enabled",
                "task_payload_json": {"keywords": ["abc12345 导流"]},
                "notes": "contact lead watch",
            },
            {
                "task_name": "DY Topic Detail",
                "platform": "dy",
                "entity_type": "content",
                "task_mode": "detail",
                "scenario_type": "topic_watch",
                "status": "draft",
                "task_payload_json": {"specified_ids": ["aweme_001"]},
                "notes": "topic propagation",
            },
            {
                "task_name": "Xianyu Seller Monitor",
                "platform": "xianyu",
                "entity_type": "seller",
                "task_mode": "monitor",
                "scenario_type": "seller_risk",
                "status": "disabled",
                "task_payload_json": {"crawler_type": "search", "keywords": ["低价手机"]},
                "runtime_payload_json": {"schedule_profile": {"cron": "0 * * * *"}, "crawler_type": "search"},
                "notes": "seller template",
            },
        ]
        for item in samples:
            response = client.post("/api/tasks", json=item)
            assert response.status_code == 200

        platform_response = client.get("/api/tasks", params={"platform": "xhs"})
        assert platform_response.status_code == 200
        assert [item["task_name"] for item in platform_response.json()["tasks"]] == ["XHS Lead Search"]

        status_response = client.get("/api/tasks", params={"status": "disabled"})
        assert status_response.status_code == 200
        assert status_response.json()["tasks"][0]["platform"] == "xianyu"

        mode_response = client.get("/api/tasks", params={"task_mode": "detail", "scenario_type": "topic_watch"})
        assert mode_response.status_code == 200
        assert mode_response.json()["tasks"][0]["task_name"] == "DY Topic Detail"

        query_response = client.get("/api/tasks", params={"q": "abc12345"})
        assert query_response.status_code == 200
        assert query_response.json()["tasks"][0]["platform"] == "xhs"

        page_response = client.get("/api/tasks", params={"limit": 1, "offset": 1})
        assert page_response.status_code == 200
        assert len(page_response.json()["tasks"]) == 1
        assert page_response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_task_list_contract_is_preserved_in_sqlite_mode(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        for index in range(3):
            response = client.post(
                "/api/tasks",
                json={
                    "task_name": f"SQLite Lead Search {index}",
                    "platform": "xhs",
                    "entity_type": "content",
                    "task_mode": "search",
                    "scenario_type": "lead_diversion",
                    "status": "enabled",
                    "task_payload_json": {"keywords": [f"sqlite_keyword_{index}"]},
                    "notes": "sqlite pagination contract",
                },
            )
            assert response.status_code == 200

        response = client.get(
            "/api/tasks",
            params={
                "platform": "xhs",
                "status": "enabled",
                "task_mode": "search",
                "entity_type": "content",
                "scenario_type": "lead_diversion",
                "q": "sqlite_keyword",
                "limit": 1,
                "offset": 1,
            },
        )

        assert response.status_code == 200
        assert set(response.json()) == {"tasks", "total"}
        assert len(response.json()["tasks"]) == 1
        assert response.json()["total"] == 3
    finally:
        set_container(original_container)


def test_crawler_diagnostics_reports_ready_command_and_validation_errors(tmp_path):
    media_root = tmp_path / "MediaCrawler"
    media_root.mkdir()
    (media_root / "main.py").write_text("print('ok')\n", encoding="utf-8")
    runner = MediaCrawlerProcessRunner(
        media_crawler_root=media_root,
        storage_root=tmp_path / "storage",
        command_prefix=["python", "main.py"],
    )
    test_container = AppContainer(tmp_path, crawler_runner=runner)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        valid_task = client.post(
            "/api/tasks",
            json={
                "task_name": "Diagnose XHS",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "task_payload_json": {"keywords": ["导流"]},
                "runtime_payload_json": {"headless": True, "cookies": "secret-cookie"},
            },
        ).json()["task"]

        valid_response = client.get(f"/api/tasks/{valid_task['id']}/crawler-diagnostics")
        assert valid_response.status_code == 200
        diagnostics = valid_response.json()["diagnostics"]
        assert diagnostics["ready"] is True
        assert "--platform" in diagnostics["command"]
        assert "<redacted>" in diagnostics["command"]
        assert diagnostics["raw_command"] == []

        invalid_task = client.post(
            "/api/tasks",
            json={
                "task_name": "Unsupported Platform",
                "platform": "xianyu",
                "entity_type": "seller",
                "task_mode": "search",
                "scenario_type": "seller_risk",
                "task_payload_json": {"keywords": ["低价手机"]},
            },
        ).json()["task"]
        invalid_response = client.get(f"/api/tasks/{invalid_task['id']}/crawler-diagnostics")
        assert invalid_response.status_code == 200
        assert invalid_response.json()["diagnostics"]["ready"] is False
        assert "no MediaCrawler entrypoint" in invalid_response.json()["diagnostics"]["errors"][0]
    finally:
        set_container(original_container)


def test_scheduled_preflight_has_no_run_or_schedule_side_effects(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        now = datetime.utcnow().replace(second=0, microsecond=0)
        task = client.post(
            "/api/tasks",
            json={
                "task_name": "Scheduled XHS Search",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "status": "enabled",
                "task_payload_json": {"keywords": ["导流"]},
                "runtime_payload_json": {"schedule_profile": {"cron": "* * * * *"}},
            },
        ).json()["task"]
        client.post(
            "/api/tasks",
            json={
                "task_name": "Disabled Scheduled Search",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "status": "disabled",
                "task_payload_json": {"keywords": ["导流"]},
                "runtime_payload_json": {"schedule_profile": {"cron": "* * * * *"}},
            },
        )
        client.post(
            "/api/tasks",
            json={
                "task_name": "Not Due Search",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "status": "enabled",
                "task_payload_json": {"keywords": ["导流"]},
                "runtime_payload_json": {"schedule_profile": {"cron": "0 0 * * *"}},
            },
        )

        first = client.post(
            "/api/tasks/run-scheduled",
            json={"now": now.isoformat(), "execute_crawler": False},
        )
        assert first.status_code == 200
        assert len(first.json()["results"]) == 1
        result = first.json()["results"][0]
        assert result["task_id"] == task["id"]
        assert result["status"] == "ready"
        assert result["reason"] == "preflight"
        assert "run" not in result

        task_after_preflight = client.get(f"/api/tasks/{task['id']}").json()["task"]
        assert task_after_preflight["last_run_at"] is None
        assert client.get(f"/api/tasks/{task['id']}/runs").json()["total"] == 0

        second = client.post(
            "/api/tasks/run-scheduled",
            json={"now": (now + timedelta(seconds=30)).isoformat(), "execute_crawler": False},
        )
        assert second.status_code == 200
        assert second.json()["results"][0]["status"] == "ready"

        third = client.post(
            "/api/tasks/run-scheduled",
            json={"now": (now + timedelta(minutes=1)).isoformat(), "execute_crawler": True},
        )
        assert third.status_code == 200
        assert len(third.json()["results"]) == 1
        assert third.json()["results"][0]["status"] == "succeeded"
        assert third.json()["results"][0]["run"]["trigger_type"] == "cron"
    finally:
        set_container(original_container)


def test_run_scheduled_tasks_records_retry_attempts_and_exhaustion(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FailingCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        now = datetime.utcnow().replace(second=0, microsecond=0)
        task = client.post(
            "/api/tasks",
            json={
                "task_name": "Retry Scheduled Search",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "status": "enabled",
                "task_payload_json": {"keywords": ["导流"]},
                "runtime_payload_json": {
                    "schedule_profile": {
                        "cron": "* * * * *",
                        "max_retries": 1,
                    }
                },
            },
        ).json()["task"]

        first = client.post(
            "/api/tasks/run-scheduled",
            json={"now": now.isoformat(), "execute_crawler": True},
        )
        assert first.status_code == 200
        first_result = first.json()["results"][0]
        assert first_result["task_id"] == task["id"]
        assert first_result["status"] == "failed"
        assert first_result["retry_attempt"] == 0
        assert first_result["run"]["run_result_json"]["max_retries"] == 1

        second = client.post(
            "/api/tasks/run-scheduled",
            json={"now": (now + timedelta(minutes=1)).isoformat(), "execute_crawler": True},
        )
        assert second.status_code == 200
        second_result = second.json()["results"][0]
        assert second_result["status"] == "failed"
        assert second_result["retry_attempt"] == 1
        assert second_result["run"]["run_result_json"]["retry_attempt"] == 1

        third = client.post(
            "/api/tasks/run-scheduled",
            json={"now": (now + timedelta(minutes=2)).isoformat(), "execute_crawler": True},
        )
        assert third.status_code == 200
        third_result = third.json()["results"][0]
        assert third_result["status"] == "skipped"
        assert third_result["reason"] == "retry_exhausted"
        assert third_result["retry_attempt"] == 1
        assert third_result["max_retries"] == 1
    finally:
        set_container(original_container)


def test_scheduler_status_endpoint_exposes_run_history(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.get("/api/tasks/scheduler/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["is_running"] is False
        assert payload["is_executing"] is False
        assert payload["queued_runs"] == 0
        assert payload["active_task_runs"] == 0
        assert payload["queued_task_runs"] == 0
        assert payload["max_concurrent_task_runs"] == 1
        assert payload["task_queue_timeout_seconds"] == 300
        assert payload["recovered_task_runs"] == 0
        assert payload["run_history"] == []
        assert payload["run_timeout_seconds"] >= 5
    finally:
        set_container(original_container)


@pytest.mark.parametrize("repository_kind", ["json", "sqlite"])
def test_container_recovers_interrupted_task_runs(tmp_path, monkeypatch, repository_kind):
    storage_dir = tmp_path / repository_kind
    monkeypatch.setenv("MEDIASPIDER_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(storage_dir / "platform.sqlite3"))
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", repository_kind)
    original_container = current_container
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    set_container(test_container)
    try:
        client = TestClient(app)
        task = client.post(
            "/api/tasks",
            json={
                "task_name": f"Interrupted {repository_kind} task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "task_payload_json": {"keywords": ["restart"]},
            },
        ).json()["task"]
        run = client.post(
            f"/api/tasks/{task['id']}/runs",
            json={"execute_crawler": False},
        ).json()["run"]
        assert run["status"] == "running"

        restored_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
        recovered = restored_container.task_service.get_run(run["id"])

        assert restored_container.task_service.recovered_task_runs == 1
        assert recovered is not None
        assert recovered.status.value == "failed"
        assert recovered.run_result_json["recovered_after_restart"] is True
        assert recovered.run_result_json["previous_status"] == "running"
        assert "backend restart" in recovered.error_message
    finally:
        set_container(original_container)


def test_task_runs_share_global_capacity_and_reject_duplicate_manual_run(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_TASK_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("MEDIASPIDER_TASK_QUEUE_TIMEOUT_SECONDS", "2")
    crawler_runner = BlockingCrawlerRunner(tmp_path)
    test_container = AppContainer(tmp_path, crawler_runner=crawler_runner)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)

        def create_task(name: str):
            return client.post(
                "/api/tasks",
                json={
                    "task_name": name,
                    "platform": "xhs",
                    "entity_type": "content",
                    "task_mode": "search",
                    "scenario_type": "lead_diversion",
                    "task_payload_json": {"keywords": [name]},
                },
            ).json()["task"]

        first_task = create_task("Capacity Task One")
        second_task = create_task("Capacity Task Two")
        service = test_container.task_service

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(service.start_run, first_task["id"])
            assert crawler_runner.started.wait(timeout=1)
            second_future = executor.submit(service.start_run, second_task["id"])
            for _ in range(100):
                if service.queued_task_runs == 1:
                    break
                time.sleep(0.01)

            assert service.active_task_runs == 1
            assert service.queued_task_runs == 1
            queued_run = service.list_runs(second_task["id"])[0]
            assert queued_run.status.value == "pending"
            assert queued_run.started_at is None

            duplicate_response = client.post(f"/api/tasks/{first_task['id']}/runs")
            assert duplicate_response.status_code == 409
            assert "already has active run" in duplicate_response.json()["detail"]

            status = client.get("/api/tasks/scheduler/status").json()
            assert status["active_task_runs"] == 1
            assert status["queued_task_runs"] == 1
            assert status["max_concurrent_task_runs"] == 1

            crawler_runner.release.set()
            first_run = first_future.result(timeout=2)
            second_run = second_future.result(timeout=2)

        assert first_run.status.value == "succeeded"
        assert second_run.status.value == "succeeded"
        assert second_run.run_result_json["queue_wait_seconds"] > 0
        assert crawler_runner.max_active_runs == 1
        assert service.active_task_runs == 0
        assert service.queued_task_runs == 0
    finally:
        set_container(original_container)


def test_pending_task_run_can_be_cancelled_without_waiting_for_capacity(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_TASK_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("MEDIASPIDER_TASK_QUEUE_TIMEOUT_SECONDS", "2")
    crawler_runner = BlockingCrawlerRunner(tmp_path)
    test_container = AppContainer(tmp_path, crawler_runner=crawler_runner)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)

        def create_task(name: str):
            return client.post(
                "/api/tasks",
                json={
                    "task_name": name,
                    "platform": "xhs",
                    "entity_type": "content",
                    "task_mode": "search",
                    "scenario_type": "lead_diversion",
                    "task_payload_json": {"keywords": [name]},
                },
            ).json()["task"]

        running_task = create_task("Running cancellation guard")
        queued_task = create_task("Queued cancellation target")
        service = test_container.task_service

        with ThreadPoolExecutor(max_workers=2) as executor:
            running_future = executor.submit(service.start_run, running_task["id"])
            assert crawler_runner.started.wait(timeout=1)
            queued_future = executor.submit(service.start_run, queued_task["id"])
            for _ in range(100):
                queued_runs = service.list_runs(queued_task["id"])
                if service.queued_task_runs == 1 and queued_runs:
                    break
                time.sleep(0.01)

            queued_run = service.list_runs(queued_task["id"])[0]
            cancel_response = client.post(
                f"/api/tasks/{queued_task['id']}/runs/{queued_run.id}/cancel"
            )
            assert cancel_response.status_code == 200
            assert cancel_response.json()["run"]["status"] == "cancelled"
            cancelled_result = queued_future.result(timeout=1)
            assert cancelled_result.status.value == "cancelled"
            assert service.queued_task_runs == 0

            running_run = service.list_runs(running_task["id"])[0]
            running_cancel = client.post(
                f"/api/tasks/{running_task['id']}/runs/{running_run.id}/cancel"
            )
            assert running_cancel.status_code == 409
            assert "Only pending task runs" in running_cancel.json()["detail"]

            crawler_runner.release.set()
            assert running_future.result(timeout=2).status.value == "succeeded"
    finally:
        set_container(original_container)


def test_manual_scheduler_run_is_persisted_in_status_history(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        run_response = client.post("/api/tasks/run-scheduled", json={"execute_crawler": False})
        assert run_response.status_code == 200

        status_response = client.get("/api/tasks/scheduler/status")
        assert status_response.status_code == 200
        history = status_response.json()["run_history"]
        assert len(history) == 1
        assert history[0]["status"] == "succeeded"
        assert history[0]["trigger_type"] == "manual"
        assert history[0]["execute_crawler"] is False

        restored_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
        set_container(restored_container)
        restored_status = client.get("/api/tasks/scheduler/status")
        assert restored_status.status_code == 200
        assert restored_status.json()["run_history"] == history
    finally:
        set_container(original_container)


def test_run_scheduled_tasks_rejects_invalid_now(tmp_path):
    test_container = AppContainer(tmp_path, crawler_runner=FakeCrawlerRunner(tmp_path))
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/tasks/run-scheduled",
            json={"now": "not-a-date", "execute_crawler": False},
        )
        assert response.status_code == 400
    finally:
        set_container(original_container)
