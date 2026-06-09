from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


@pytest.mark.parametrize("path", ["/health", "/api/health"])
def test_health_check_reports_ok(path: str) -> None:
    client = TestClient(app)

    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
