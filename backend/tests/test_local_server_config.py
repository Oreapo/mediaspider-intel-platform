from __future__ import annotations

import os

import pytest

from backend.app.__main__ import (
    DEFAULT_BACKEND_HOST,
    DEFAULT_BACKEND_PORT,
    backend_server_config,
    load_local_environment,
)


def test_local_server_config_uses_safe_development_defaults(monkeypatch):
    monkeypatch.delenv("MEDIASPIDER_BACKEND_HOST", raising=False)
    monkeypatch.delenv("MEDIASPIDER_BACKEND_PORT", raising=False)
    monkeypatch.delenv("MEDIASPIDER_BACKEND_RELOAD", raising=False)

    assert backend_server_config() == (DEFAULT_BACKEND_HOST, DEFAULT_BACKEND_PORT, True)


def test_local_server_config_reads_environment_overrides(monkeypatch):
    monkeypatch.setenv("MEDIASPIDER_BACKEND_HOST", "0.0.0.0")
    monkeypatch.setenv("MEDIASPIDER_BACKEND_PORT", "9000")
    monkeypatch.setenv("MEDIASPIDER_BACKEND_RELOAD", "false")

    assert backend_server_config() == ("0.0.0.0", 9000, False)


def test_local_environment_loads_dotenv_without_overriding_shell_values(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "MEDIASPIDER_BACKEND_HOST=0.0.0.0\n"
        "MEDIASPIDER_BACKEND_PORT=9001\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIASPIDER_BACKEND_HOST", "127.0.0.1")
    monkeypatch.delenv("MEDIASPIDER_BACKEND_PORT", raising=False)

    load_local_environment(env_path)

    assert os.environ["MEDIASPIDER_BACKEND_HOST"] == "127.0.0.1"
    assert os.environ["MEDIASPIDER_BACKEND_PORT"] == "9001"


@pytest.mark.parametrize("value", ["invalid", "0", "65536"])
def test_local_server_config_rejects_invalid_ports(monkeypatch, value):
    monkeypatch.setenv("MEDIASPIDER_BACKEND_PORT", value)

    with pytest.raises(ValueError, match="MEDIASPIDER_BACKEND_PORT"):
        backend_server_config()
