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


def test_hash_password_roundtrip_and_backward_compat():
    from app.application.auth_service import AuthService

    service = AuthService.__new__(AuthService)
    hashed_a = AuthService.hash_password("s3cret!")
    hashed_b = AuthService.hash_password("s3cret!")

    assert hashed_a.startswith("pbkdf2_sha256$")
    assert ":" not in hashed_a  # safe inside MEDIASPIDER_AUTH_USERS
    assert hashed_a != hashed_b  # unique salt per hash
    assert service._verify_password("s3cret!", hashed_a)
    assert not service._verify_password("wrong", hashed_a)
    # Plaintext still verifies for backward compatibility.
    assert service._verify_password("plain", "plain")
    assert not service._verify_password("plain", "other")


def test_login_with_hashed_password(tmp_path, monkeypatch):
    from app.application.auth_service import AuthService

    hashed = AuthService.hash_password("s3cret!")
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", f"analyst:{hashed}:analyst:Risk Analyst")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        ok = client.post("/api/auth/login", json={"username": "analyst", "password": "s3cret!"})
        assert ok.status_code == 200
        assert ok.json()["user"]["role"] == "analyst"

        bad = client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"})
        assert bad.status_code == 401
    finally:
        set_container(original_container)


def test_login_rate_limited_after_repeated_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_AUTH_REQUIRED", "true")
    monkeypatch.setenv("MEDIASPIDER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("MEDIASPIDER_AUTH_USERS", "analyst:secret:analyst:Risk Analyst")
    monkeypatch.setenv("MEDIASPIDER_AUTH_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("MEDIASPIDER_AUTH_LOCKOUT_SECONDS", "300")
    test_container = AppContainer(tmp_path)
    original_container = current_container
    set_container(test_container)
    try:
        client = TestClient(app)
        for _ in range(3):
            bad = client.post("/api/auth/login", json={"username": "analyst", "password": "wrong"})
            assert bad.status_code == 401

        # Further attempts are locked out, even with the correct password.
        locked = client.post("/api/auth/login", json={"username": "analyst", "password": "secret"})
        assert locked.status_code == 429
        assert "Retry-After" in locked.headers
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

        task_id = operator_task_response.json()["task"]["id"]
        analyst_retry_response = client.post(
            f"/api/tasks/{task_id}/runs/missing-run/retry",
            headers=analyst_headers,
        )
        assert analyst_retry_response.status_code == 403

        operator_retry_response = client.post(
            f"/api/tasks/{task_id}/runs/missing-run/retry",
            headers=operator_headers,
        )
        assert operator_retry_response.status_code == 404

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
