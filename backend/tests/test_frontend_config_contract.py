from __future__ import annotations

import re
from pathlib import Path

from backend.app.main import DEFAULT_CORS_ORIGINS


ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"
FRONTEND_SRC = ROOT / "frontend" / "src"
FRONTEND_API_DIR = FRONTEND_SRC / "api"
FRONTEND_HTTP_CLIENT = FRONTEND_SRC / "lib" / "http.ts"
FRONTEND_VITE_CONFIG = ROOT / "frontend" / "vite.config.ts"
FRONTEND_SETTINGS_VIEW = FRONTEND_SRC / "views" / "SettingsView.vue"
FRONTEND_TASKS_VIEW = FRONTEND_SRC / "views" / "TasksView.vue"
DOCKER_COMPOSE = ROOT / "docker-compose.yml"
CRAWLER_DOCKER_COMPOSE = ROOT / "docker-compose.crawler.yml"
BACKEND_DOCKERFILE = ROOT / "backend" / "Dockerfile"
CRAWLER_BACKEND_DOCKERFILE = ROOT / "backend" / "Dockerfile.crawler"
FRONTEND_NGINX_CONFIG = ROOT / "frontend" / "nginx.conf"
DEFAULT_BACKEND_TARGET = "http://127.0.0.1:8180"
VITE_FRONTEND_ORIGINS = {
    "http://127.0.0.1:5200",
    "http://localhost:5200",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
}
DOCKER_FRONTEND_ORIGINS = {"http://localhost:8080"}
FRONTEND_ORIGINS = VITE_FRONTEND_ORIGINS | DOCKER_FRONTEND_ORIGINS
VITE_PROXY_PATHS = {"/api", "/health"}


def test_default_cors_origins_cover_local_frontends():
    assert FRONTEND_ORIGINS.issubset(set(DEFAULT_CORS_ORIGINS))


def test_env_example_cors_origins_cover_local_frontends():
    env_values = _read_env_example()
    configured_origins = {
        origin.strip()
        for origin in env_values["MEDIASPIDER_CORS_ORIGINS"].split(",")
        if origin.strip()
    }

    assert FRONTEND_ORIGINS.issubset(configured_origins)
    assert env_values["MEDIASPIDER_BACKEND_HOST"] == "127.0.0.1"
    assert env_values["MEDIASPIDER_BACKEND_PORT"] == "8180"
    assert env_values["MEDIASPIDER_BACKEND_RELOAD"] == "true"
    assert env_values["MEDIASPIDER_STORAGE_DIR"] == "backend/storage"
    assert env_values["MEDIASPIDER_SQLITE_PATH"] == "backend/storage/mediaspider-intel.sqlite3"
    assert env_values["MEDIASPIDER_API_TARGET"] == DEFAULT_BACKEND_TARGET
    assert env_values["MEDIASPIDER_FRONTEND_PORT"] == "5200"
    assert env_values["MEDIASPIDER_FRONTEND_URL"] == "http://127.0.0.1:5200"
    assert env_values["VITE_API_BASE_URL"] == "/api"
    assert "MEDIASPIDER_MEDIA_CRAWLER_COMMAND" in env_values
    assert "MEDIASPIDER_MEDIA_CRAWLER_HOST_PATH" in env_values


def test_vite_proxy_uses_default_backend_target_for_dev_and_preview():
    config = FRONTEND_VITE_CONFIG.read_text(encoding="utf-8")

    assert "loadEnv(mode, projectRoot, '')" in config
    assert re.search(r"process\.env\.MEDIASPIDER_API_TARGET\s*\|\|\s*env\.MEDIASPIDER_API_TARGET", config)
    assert DEFAULT_BACKEND_TARGET in config
    for proxy_path in VITE_PROXY_PATHS:
        assert re.search(
            rf"['\"]{re.escape(proxy_path)}['\"]\s*:\s*\{{\s*target:\s*apiTarget,\s*changeOrigin:\s*true",
            config,
            re.S,
        )
    assert re.search(r"server:\s*\{.*?proxy:\s*apiProxy", config, re.S)
    assert "MEDIASPIDER_FRONTEND_PORT" in config
    assert re.search(r"preview:\s*\{.*?proxy:\s*apiProxy", config, re.S)


def test_vite_config_pins_frontend_root_for_local_dev_server():
    config = FRONTEND_VITE_CONFIG.read_text(encoding="utf-8")

    assert "fileURLToPath(new URL('.', import.meta.url))" in config
    assert "fileURLToPath(new URL('..', import.meta.url))" in config
    assert re.search(r"root:\s*frontendRoot", config)
    assert re.search(r"envDir:\s*projectRoot", config)
    assert re.search(r"fs:\s*\{\s*allow:\s*\[\s*frontendRoot\s*\]", config, re.S)


def test_docker_network_keeps_backend_container_port():
    compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
    backend_dockerfile = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    nginx = FRONTEND_NGINX_CONFIG.read_text(encoding="utf-8")

    assert '"${MEDIASPIDER_BACKEND_PORT:-8180}:8000"' in compose
    assert 'MEDIASPIDER_AUTO_MIGRATE_JSON: "true"' in compose
    assert "MEDIASPIDER_ANALYSIS_REPOSITORY: sqlite" in compose
    assert "MEDIASPIDER_PLATFORM_PROFILE_REPOSITORY: sqlite" in compose
    assert "MEDIASPIDER_AUDIT_REPOSITORY: sqlite" in compose
    assert 'CMD ["python", "scripts/start_backend.py"]' in backend_dockerfile
    assert "127.0.0.1:8000/health" in compose
    assert "http://backend:8000/api/" in nginx
    assert "http://backend:8000/health" in nginx


def test_crawler_docker_overlay_packages_runtime_and_browser():
    compose = CRAWLER_DOCKER_COMPOSE.read_text(encoding="utf-8")
    dockerfile = CRAWLER_BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "backend/Dockerfile.crawler" in compose
    assert "additional_contexts:" in compose
    assert "MEDIASPIDER_MEDIA_CRAWLER_HOST_PATH" in compose
    assert "MEDIASPIDER_MEDIA_CRAWLER_ROOT: /opt/mediacrawler" in compose
    assert "MEDIASPIDER_MEDIA_CRAWLER_COMMAND: python /app/backend/scripts/run_mediacrawler.py" in compose
    assert "mediaspider-browser-data:/opt/mediacrawler/browser_data" in compose
    assert 'shm_size: "1gb"' in compose
    assert "chromium" in dockerfile
    assert "requirements-mediacrawler.txt" in dockerfile
    assert "COPY --from=mediacrawler . /opt/mediacrawler" in dockerfile
    assert 'ENTRYPOINT ["dumb-init", "--"]' in dockerfile


def test_frontend_api_base_url_is_centralized_in_http_client():
    direct_references = [
        source
        for source in _frontend_source_files()
        if source != FRONTEND_HTTP_CLIENT and "VITE_API_BASE_URL" in source.read_text(encoding="utf-8")
    ]

    assert direct_references == []


def test_frontend_fetch_is_centralized_in_http_client():
    direct_fetches = [
        source
        for source in _frontend_source_files()
        if source != FRONTEND_HTTP_CLIENT and "fetch(" in source.read_text(encoding="utf-8")
    ]

    assert direct_fetches == []


def test_frontend_http_client_normalizes_fastapi_error_payloads():
    client = FRONTEND_HTTP_CLIENT.read_text(encoding="utf-8")

    assert "function errorMessageFromPayload" in client
    assert "function formatErrorDetail" in client
    assert re.search(r"Array\.isArray\(detail\).*?formatErrorDetail\(item\)", client, re.S)
    assert "record.msg" in client
    assert "record.loc" in client
    assert "errorMessageFromPayload(data) || 'Request failed'" in client


def test_frontend_http_client_clears_auth_token_on_unauthorized():
    client = FRONTEND_HTTP_CLIENT.read_text(encoding="utf-8")

    assert re.search(r"response\.status\s*===\s*401\)\s*clearAuthToken\(\)", client)


def test_frontend_http_calls_are_centralized_in_api_modules():
    direct_http_calls = [
        source
        for source in _frontend_source_files()
        if not _is_relative_to(source, FRONTEND_API_DIR)
        and re.search(r"\bhttp\.(?:get|post|patch|delete)\b", source.read_text(encoding="utf-8"))
    ]

    assert direct_http_calls == []


def test_frontend_download_calls_are_centralized_in_api_modules():
    direct_download_calls = [
        source
        for source in _frontend_source_files()
        if source != FRONTEND_HTTP_CLIENT
        and not _is_relative_to(source, FRONTEND_API_DIR)
        and re.search(r"\bdownloadApiFile\s*\(", source.read_text(encoding="utf-8"))
    ]

    assert direct_download_calls == []


def test_frontend_downloads_reuse_authenticated_error_handling():
    client = FRONTEND_HTTP_CLIENT.read_text(encoding="utf-8")

    assert "export async function downloadApiFile" in client
    assert re.search(r"downloadApiFile.*?authorizedFetch\(path\)", client, re.S)
    assert re.search(r"!response\.ok\)\s*throw await responseError\(response\)", client)
    assert "response.headers.get('Content-Disposition')" in client
    assert "URL.createObjectURL(blob)" in client
    assert "URL.revokeObjectURL(objectUrl)" in client


def test_settings_platform_profile_options_use_backend_platform_models():
    settings_view = FRONTEND_SETTINGS_VIEW.read_text(encoding="utf-8")

    assert "usePlatformModels" in settings_view
    assert re.search(r'v-for="item in profilePlatformOptions"', settings_view)
    assert re.findall(r'<option\s+value=["\'](?:xhs|dy|ks|bili|wb|tieba|zhihu|xianyu)["\']', settings_view) == []


def test_task_creation_form_sends_crawler_runtime_and_storage_options():
    tasks_view = FRONTEND_TASKS_VIEW.read_text(encoding="utf-8")

    for text in [
        "auth_profile_id: form.value.auth_profile_id || null",
        "signal_extractors: toStringList(form.value.signal_extractors)",
        "login_type: form.value.login_type",
        "save_option: form.value.save_option",
        "max_comments_count_singlenotes: form.value.max_comments_count_singlenotes",
        "max_concurrency_num: form.value.max_concurrency_num",
    ]:
        assert text in tasks_view

    assert "usePlatformProfiles" in tasks_view
    assert "profile.platform === form.value.platform" in tasks_view
    assert "profile.auth_type !== 'state_file'" in tasks_view


def _frontend_source_files() -> list[Path]:
    return [*FRONTEND_SRC.rglob("*.ts"), *FRONTEND_SRC.rglob("*.vue")]


def _is_relative_to(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def _read_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values
