from __future__ import annotations

from pathlib import Path

from ..domain.models.task import TaskRun
from .task_service import CollectionTaskService


class LogService:
    def __init__(self, task_service: CollectionTaskService, storage_root: Path):
        self.task_service = task_service
        self.storage_root = storage_root

    def list_run_logs(self) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for run in self.task_service.list_runs():
            entries.append(
                {
                    "run": run.model_dump(mode="json"),
                    "has_log": self._log_exists(run),
                    "log_size": self._log_size(run),
                }
            )
        return entries

    def read_run_log(self, run_id: str, max_lines: int = 400) -> dict[str, object]:
        run = self.task_service.get_run(run_id)
        if run is None:
            raise ValueError(f"Task run {run_id} not found")
        if not run.log_path:
            raise ValueError(f"Task run {run_id} has no log path")
        log_path = self._resolve_log_path(run.log_path)
        if not log_path.exists() or not log_path.is_file():
            raise ValueError(f"Task run log not found: {run_id}")
        text = log_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        limited_lines = lines[-max_lines:] if max_lines > 0 else lines
        return {
            "run": run.model_dump(mode="json"),
            "log_path": str(log_path),
            "line_count": len(lines),
            "truncated": max_lines > 0 and len(lines) > len(limited_lines),
            "content": "\n".join(limited_lines),
        }

    def _log_exists(self, run: TaskRun) -> bool:
        if not run.log_path:
            return False
        try:
            path = self._resolve_log_path(run.log_path)
        except ValueError:
            return False
        return path.exists() and path.is_file()

    def _log_size(self, run: TaskRun) -> int:
        if not self._log_exists(run):
            return 0
        return self._resolve_log_path(run.log_path).stat().st_size

    def _resolve_log_path(self, log_path: str) -> Path:
        path = Path(log_path)
        resolved = path.resolve() if path.is_absolute() else (self.storage_root / path).resolve()
        resolved.relative_to(self.storage_root.resolve())
        return resolved
