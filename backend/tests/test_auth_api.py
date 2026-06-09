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


def _auth_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_login_and_me_with_configured_user(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", "analyst:secret:analyst:Risk Analyst")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        login_response = client.post("/api/auth/login", json={"username": "analyst", "password": "secret"})
        assert login_response.status_code == 200
        payload = login_response.json()
        assert payload["user"]["role"] == "analyst"
        assert payload["token_type"] == "bearer"

        me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload['token']}"})
        assert me_response.status_code == 200
        assert me_response.json()["display_name"] == "Risk Analyst"
    finally:
        set_container(original_container)


def test_me_requires_token_when_auth_required(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.get("/api/auth/me")
        assert response.status_code == 401
    finally:
        set_container(original_container)


def test_me_returns_development_user_when_auth_not_required(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "false")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["username"] == "anonymous"
    finally:
        set_container(original_container)


def test_core_api_requires_token_when_auth_required(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 401
    finally:
        set_container(original_container)


def test_core_api_accepts_query_access_token_for_download_links(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", "viewer:secret:viewer:Read Only")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        token = client.post("/api/auth/login", json={"username": "viewer", "password": "secret"}).json()["token"]
        response = client.get("/api/dashboard/summary", params={"access_token": token})
        assert response.status_code == 200
    finally:
        set_container(original_container)


def test_viewer_can_read_but_cannot_write(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", "viewer:secret:viewer:Read Only")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        headers = _auth_headers(client, "viewer", "secret")

        read_response = client.get("/api/datasets", headers=headers)
        assert read_response.status_code == 200

        write_response = client.post(
            "/api/datasets",
            json={
                "dataset_name": "readonly attempt",
                "dataset_type": "raw",
                "source_platform": "xhs",
                "storage_uri": "",
                "tags": [],
            },
            headers=headers,
        )
        assert write_response.status_code == 403
    finally:
        set_container(original_container)


def test_role_specific_write_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv(
        "MEDIASPIDER_AUTH_USERS",
        "analyst:secret:analyst:Analyst,operator:secret:operator:Operator",
    )
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        analyst_headers = _auth_headers(client, "analyst", "secret")
        operator_headers = _auth_headers(client, "operator", "secret")

        operator_task_response = client.post(
            "/api/tasks",
            json={
                "task_name": "operator task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "task_payload_json": {"keywords": ["risk"]},
            },
            headers=operator_headers,
        )
        assert operator_task_response.status_code == 200

        analyst_task_response = client.post(
            "/api/tasks",
            json={
                "task_name": "analyst task",
                "platform": "xhs",
                "entity_type": "content",
                "task_mode": "search",
                "scenario_type": "lead_diversion",
                "task_payload_json": {"keywords": ["risk"]},
            },
            headers=analyst_headers,
        )
        assert analyst_task_response.status_code == 403

        analyst_case_response = client.post(
            "/api/cases",
            json={
                "case_name": "analyst case",
                "case_type": "lead_diversion",
                "priority": "medium",
                "summary": "",
            },
            headers=analyst_headers,
        )
        assert analyst_case_response.status_code == 200

        operator_case_response = client.post(
            "/api/cases",
            json={
                "case_name": "operator case",
                "case_type": "lead_diversion",
                "priority": "medium",
                "summary": "",
            },
            headers=operator_headers,
        )
        assert operator_case_response.status_code == 403
    finally:
        set_container(original_container)
