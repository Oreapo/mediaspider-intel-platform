from __future__ import annotations

import os

import pytest

from backend.app.__main__ import (
    DEFAULT_BACKEND_HOST,
    DEFAULT_BACKEND_PORT,
    backend_server_config,
    load_local_environment,
)
from backend.app.api.dependencies.container import AppContainer


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


def test_container_resolves_relative_storage_paths_from_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "mediaspider-intel-platform"
    backend_root = project_root / "backend"
    backend_root.mkdir(parents=True)
    monkeypatch.setenv("MEDIASPIDER_STORAGE_DIR", "backend/storage")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", "backend/storage/app.sqlite3")
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "json")

    container = AppContainer(backend_root)

    assert container.storage_dir == (project_root / "backend" / "storage").resolve()
    assert container._sqlite_path() == (project_root / "backend" / "storage" / "app.sqlite3").resolve()


def test_container_uses_configured_media_crawler_command(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIASPIDER_MEDIA_CRAWLER_COMMAND", "python main.py")
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "json")

    container = AppContainer(tmp_path)

    assert container._crawler_runner.command_prefix == ["python", "main.py"]


@pytest.mark.parametrize("value", ["invalid", "0", "65536"])
def test_local_server_config_rejects_invalid_ports(monkeypatch, value):
    monkeypatch.setenv("MEDIASPIDER_BACKEND_PORT", value)

    with pytest.raises(ValueError, match="MEDIASPIDER_BACKEND_PORT"):
        backend_server_config()
