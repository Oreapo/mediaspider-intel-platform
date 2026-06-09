from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ..domain.models.task import CollectionTask, TaskMode, TaskRun


SUPPORTED_CRAWLER_PLATFORMS = {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}
SUPPORTED_FILE_SAVE_OPTIONS = {"jsonl", "json", "csv"}
OUTPUT_EXTENSIONS = {".jsonl", ".json", ".csv"}


@dataclass
class CrawlerRunResult:
    return_code: int
    log_path: Path
    output_files: list[Path] = field(default_factory=list)
    command: list[str] = field(default_factory=list)
    redacted_command: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str = ""


class CrawlerRunner(Protocol):
    def run(self, task: CollectionTask, run: TaskRun) -> CrawlerRunResult:
        ...


class MediaCrawlerProcessRunner:
    def __init__(
        self,
        *,
        media_crawler_root: Path,
        storage_root: Path,
        command_prefix: list[str] | None = None,
    ):
        self.media_crawler_root = media_crawler_root
        self.storage_root = storage_root
        self.command_prefix = command_prefix or ["uv", "run", "python", "main.py"]

    def run(self, task: CollectionTask, run: TaskRun) -> CrawlerRunResult:
        self._validate_root()
        started_at = datetime.utcnow()
        output_root = self.storage_root / "crawler_run_outputs" / run.id
        output_root.mkdir(parents=True, exist_ok=True)
        log_path = self.storage_root / "crawler_logs" / f"{run.id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        command, redacted_command = self._build_command(task, output_root)
        timeout_seconds = self._positive_int(
            task.runtime_payload_json.get("timeout_seconds"),
            default=3600,
            minimum=30,
        )

        log_lines = [
            f"run_id={run.id}",
            f"task_id={task.id}",
            f"started_at={started_at.isoformat()}",
            "command=" + " ".join(redacted_command),
            "",
        ]
        log_path.write_text("\n".join(log_lines), encoding="utf-8")

        try:
            completed = subprocess.run(
                command,
                cwd=self.media_crawler_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            finished_at = datetime.utcnow()
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(completed.stdout or "")
                handle.write("\n")
                handle.write(f"finished_at={finished_at.isoformat()}\n")
                handle.write(f"return_code={completed.returncode}\n")
            return CrawlerRunResult(
                return_code=completed.returncode,
                log_path=log_path,
                output_files=self._discover_output_files(output_root),
                command=command,
                redacted_command=redacted_command,
                started_at=started_at,
                finished_at=finished_at,
                error_message="" if completed.returncode == 0 else f"MediaCrawler exited with code {completed.returncode}",
            )
        except subprocess.TimeoutExpired as exc:
            finished_at = datetime.utcnow()
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(exc.stdout or "")
                handle.write("\n")
                handle.write(f"finished_at={finished_at.isoformat()}\n")
                handle.write(f"timeout_seconds={timeout_seconds}\n")
            return CrawlerRunResult(
                return_code=124,
                log_path=log_path,
                output_files=self._discover_output_files(output_root),
                command=command,
                redacted_command=redacted_command,
                started_at=started_at,
                finished_at=finished_at,
                error_message=f"MediaCrawler timed out after {timeout_seconds} seconds",
            )

    def diagnose(self, task: CollectionTask, run_id: str = "dry-run") -> dict[str, object]:
        output_root = self.storage_root / "crawler_run_outputs" / run_id
        log_path = self.storage_root / "crawler_logs" / f"{run_id}.log"
        errors: list[str] = []
        warnings: list[str] = []
        command: list[str] = []
        redacted_command: list[str] = []

        if not (self.media_crawler_root / "main.py").exists():
            errors.append(f"MediaCrawler root not found: {self.media_crawler_root}")
        try:
            command, redacted_command = self._build_command(task, output_root)
        except ValueError as exc:
            errors.append(str(exc))

        if task.runtime_payload_json.get("cookies"):
            warnings.append("cookies are configured and will be redacted from diagnostics")
        if task.runtime_payload_json.get("state_file"):
            warnings.append("state_file is configured on the profile; MediaCrawler CLI cookie support is used when cookies are present")
        if not task.runtime_payload_json.get("headless", False):
            warnings.append("headless is disabled; server environments may require a visible browser session")

        return {
            "ready": not errors,
            "media_crawler_root": str(self.media_crawler_root),
            "output_root": str(output_root),
            "log_path": str(log_path),
            "command": redacted_command,
            "raw_command": command if not task.runtime_payload_json.get("cookies") else [],
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_root(self) -> None:
        if not (self.media_crawler_root / "main.py").exists():
            raise ValueError(f"MediaCrawler root not found: {self.media_crawler_root}")

    def _build_command(self, task: CollectionTask, output_root: Path) -> tuple[list[str], list[str]]:
        platform = task.platform.value
        if platform not in SUPPORTED_CRAWLER_PLATFORMS:
            raise ValueError(f"Platform {platform} has no MediaCrawler entrypoint yet")

        crawler_type = self._resolve_crawler_type(task)
        save_option = str(task.storage_profile_json.get("save_option") or "jsonl").lower()
        if save_option not in SUPPORTED_FILE_SAVE_OPTIONS:
            raise ValueError(f"Task storage save_option must be one of {sorted(SUPPORTED_FILE_SAVE_OPTIONS)}")

        command = [
            *self.command_prefix,
            "--platform",
            platform,
            "--type",
            crawler_type,
            "--start",
            str(self._positive_int(task.filter_payload_json.get("start_page") or task.runtime_payload_json.get("start_page"), 1, 1)),
            "--save_data_option",
            save_option,
            "--save_data_path",
            str(output_root),
            "--get_comment",
            self._bool_string(task.runtime_payload_json.get("enable_comments", True)),
            "--get_sub_comment",
            self._bool_string(task.runtime_payload_json.get("enable_sub_comments", False)),
            "--headless",
            self._bool_string(task.runtime_payload_json.get("headless", False)),
            "--max_comments_count_singlenotes",
            str(self._positive_int(task.runtime_payload_json.get("max_comments_count_singlenotes"), 10, 0)),
            "--max_concurrency_num",
            str(self._positive_int(task.runtime_payload_json.get("max_concurrency_num"), 1, 1)),
            "--enable_ip_proxy",
            self._bool_string(task.runtime_payload_json.get("enable_ip_proxy", False)),
        ]

        proxy_provider = task.runtime_payload_json.get("ip_proxy_provider_name")
        if proxy_provider:
            command.extend(["--ip_proxy_provider_name", str(proxy_provider)])
        proxy_pool_count = task.runtime_payload_json.get("ip_proxy_pool_count")
        if proxy_pool_count:
            command.extend(["--ip_proxy_pool_count", str(self._positive_int(proxy_pool_count, 2, 1))])

        if crawler_type == "search":
            keywords = self._string_list(task.task_payload_json.get("keywords"))
            if not keywords:
                raise ValueError("search crawler requires task_payload_json.keywords")
            command.extend(["--keywords", ",".join(keywords)])
        elif crawler_type == "detail":
            specified_ids = self._string_list(task.task_payload_json.get("specified_ids"))
            if not specified_ids:
                raise ValueError("detail crawler requires task_payload_json.specified_ids")
            command.extend(["--specified_id", ",".join(specified_ids)])
        elif crawler_type == "creator":
            creator_ids = self._string_list(task.task_payload_json.get("creator_ids"))
            if not creator_ids:
                raise ValueError("creator crawler requires task_payload_json.creator_ids")
            command.extend(["--creator_id", ",".join(creator_ids)])

        cookies = task.runtime_payload_json.get("cookies")
        redacted_command = list(command)
        if cookies:
            command.extend(["--cookies", str(cookies)])
            redacted_command.extend(["--cookies", "<redacted>"])
        return command, redacted_command

    def _resolve_crawler_type(self, task: CollectionTask) -> str:
        if task.task_mode != TaskMode.MONITOR:
            return task.task_mode.value
        configured = task.runtime_payload_json.get("crawler_type") or task.task_payload_json.get("crawler_type")
        if configured not in {"search", "detail", "creator"}:
            raise ValueError("monitor task runs require runtime_payload_json.crawler_type to be search, detail, or creator")
        return str(configured)

    def _discover_output_files(self, output_root: Path) -> list[Path]:
        if not output_root.exists():
            return []
        files = [
            file_path
            for file_path in output_root.rglob("*")
            if file_path.is_file() and file_path.suffix.lower() in OUTPUT_EXTENSIONS and file_path.stat().st_size > 0
        ]
        return sorted(files)

    def _string_list(self, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _bool_string(self, value: object) -> str:
        if isinstance(value, str):
            return "true" if value.lower() in {"1", "true", "yes", "y"} else "false"
        return "true" if bool(value) else "false"

    def _positive_int(self, value: object, default: int, minimum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(parsed, minimum)
