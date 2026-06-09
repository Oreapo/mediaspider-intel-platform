from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


DEFAULT_BACKEND_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 8180
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_local_environment(env_path: Path | None = None) -> None:
    load_dotenv(env_path or PROJECT_ROOT / ".env", override=False)


def backend_server_config() -> tuple[str, int, bool]:
    host = os.getenv("MEDIASPIDER_BACKEND_HOST", DEFAULT_BACKEND_HOST).strip() or DEFAULT_BACKEND_HOST
    raw_port = os.getenv("MEDIASPIDER_BACKEND_PORT", str(DEFAULT_BACKEND_PORT)).strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("MEDIASPIDER_BACKEND_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("MEDIASPIDER_BACKEND_PORT must be between 1 and 65535")
    reload_enabled = os.getenv("MEDIASPIDER_BACKEND_RELOAD", "true").strip().lower() == "true"
    return host, port, reload_enabled


def main() -> None:
    load_local_environment()
    host, port, reload_enabled = backend_server_config()
    uvicorn.run(
        f"{__package__}.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
