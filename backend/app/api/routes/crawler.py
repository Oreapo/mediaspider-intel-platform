from __future__ import annotations

from datetime import datetime
from threading import RLock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import OPERATOR_ROLES, READ_ROLES, get_log_service, get_task_service, require_roles
from ..schemas.crawler import CrawlerLogEntry, CrawlerStartRequest, CrawlerStatusResponse
from ..schemas.task import CollectionTaskCreateRequest
from ...application.log_service import LogService
from ...application.task_service import CollectionTaskService
from ...domain.models.task import TaskRunStatus


router = APIRouter(prefix="/crawler", tags=["crawler"], dependencies=[Depends(require_roles(*READ_ROLES))])


class _CrawlerCompatState:
    def __init__(self) -> None:
        self._lock = RLock()
        self.task_id: str | None = None
        self.run_id: str | None = None
        self.config: CrawlerStartRequest | None = None
        self.accepted_at: float = 0.0

    def set_current(self, *, task_id: str, run_id: str, config: CrawlerStartRequest) -> None:
        with self._lock:
            self.task_id = task_id
            self.run_id = run_id
            self.config = config
            self.accepted_at = monotonic()

    def snapshot(self) -> tuple[str | None, str | None, CrawlerStartRequest | None, float]:
        with self._lock:
            return self.task_id, self.run_id, self.config, self.accepted_at

_compat_state = _CrawlerCompatState()


@router.post("/start", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def start_crawler(
    payload: CrawlerStartRequest,
    service: CollectionTaskService = Depends(get_task_service),
):
    task_id, run_id, _, _ = _compat_state.snapshot()
    if run_id:
        existing_run = service.get_run(run_id)
        if existing_run is not None and existing_run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
            raise HTTPException(status_code=409, detail="Crawler is already running")

    try:
        task = service.create_task(_task_request_from_crawler_payload(payload))
        run = service.submit_run(task.id, trigger_type="crawler_api", execute_crawler=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _compat_state.set_current(task_id=task.id, run_id=run.id, config=payload)
    return {
        "message": "Crawler run accepted",
        "task_id": task.id,
        "run_id": run.id,
        "status": run.status.value,
    }


@router.post("/stop", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def stop_crawler(service: CollectionTaskService = Depends(get_task_service)):
    task_id, run_id, _, _ = _compat_state.snapshot()
    if not task_id or not run_id:
        return {"message": "Crawler is not running", "stopped": False}
    try:
        run = service.cancel_run(task_id, run_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {
        "message": "Crawler stop requested",
        "stopped": True,
        "task_id": task_id,
        "run_id": run.id,
        "status": run.status.value,
    }


@router.get("/status", response_model=CrawlerStatusResponse)
def get_crawler_status(service: CollectionTaskService = Depends(get_task_service)):
    task_id, run_id, config, accepted_at = _compat_state.snapshot()
    if not task_id or not run_id:
        return CrawlerStatusResponse(status="idle")
    run = service.get_run(run_id)
    if run is None:
        return CrawlerStatusResponse(
            status="running" if monotonic() - accepted_at < 5 else "idle",
            platform=config.platform if config else None,
            crawler_type=config.crawler_type if config else None,
            task_id=task_id,
            run_id=run_id,
        )

    if run.status in {TaskRunStatus.PENDING, TaskRunStatus.RUNNING}:
        status_value = "running"
    elif run.status == TaskRunStatus.FAILED:
        status_value = "error"
    else:
        status_value = "idle"
    return CrawlerStatusResponse(
        status=status_value,
        platform=config.platform if config else None,
        crawler_type=config.crawler_type if config else None,
        started_at=run.started_at,
        error_message=run.error_message or None,
        task_id=task_id,
        run_id=run_id,
    )


@router.get("/logs")
def list_crawler_logs(
    max_lines: int = Query(400, ge=1, le=2000),
    service: CollectionTaskService = Depends(get_task_service),
    log_service: LogService = Depends(get_log_service),
):
    _, run_id, _, _ = _compat_state.snapshot()
    if not run_id or service.get_run(run_id) is None:
        return {"logs": []}
    try:
        log = log_service.read_run_log(run_id, max_lines=max_lines)
    except ValueError:
        return {"logs": []}
    return {
        "logs": [
            entry.model_dump(mode="json")
            for entry in _entries_from_log_content(log.get("content", ""))
        ],
        "line_count": log.get("line_count", 0),
        "truncated": log.get("truncated", False),
    }


def _task_request_from_crawler_payload(payload: CrawlerStartRequest) -> CollectionTaskCreateRequest:
    task_payload: dict[str, object]
    if payload.crawler_type == "search":
        task_payload = {"keywords": _split_csv(payload.keywords)}
    elif payload.crawler_type == "detail":
        task_payload = {"specified_ids": _split_csv(payload.specified_ids)}
    else:
        task_payload = {"creator_ids": _split_csv(payload.creator_ids)}

    runtime_payload = {
        "login_type": payload.login_type,
        "start_page": payload.start_page,
        "enable_comments": payload.enable_comments,
        "enable_sub_comments": payload.enable_sub_comments,
        "headless": payload.headless,
        "max_comments_count_singlenotes": payload.max_comments_count_singlenotes,
        "max_concurrency_num": payload.max_concurrency_num,
    }
    if payload.cookies:
        runtime_payload["cookies"] = payload.cookies

    return CollectionTaskCreateRequest(
        task_name=f"MediaCrawler {payload.platform} {payload.crawler_type} {datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        platform=payload.platform,
        entity_type="creator" if payload.crawler_type == "creator" else "content",
        task_mode=payload.crawler_type,
        scenario_type="lead_diversion",
        task_payload_json=task_payload,
        filter_payload_json={"start_page": payload.start_page},
        runtime_payload_json=runtime_payload,
        storage_profile_json={"save_option": payload.save_option},
        analysis_profile_json={
            "signal_extractors": ["risk_terms", "contact_points"],
            "analysis_types": ["signal_summary"],
        },
        notes="Created through MediaSpiderGUI-compatible crawler API.",
    )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _entries_from_log_content(content: str) -> list[CrawlerLogEntry]:
    entries: list[CrawlerLogEntry] = []
    for index, line in enumerate([item for item in content.splitlines() if item.strip()], start=1):
        entries.append(
            CrawlerLogEntry(
                id=index,
                timestamp="",
                level=_parse_log_level(line),
                message=line,
            )
        )
    return entries


def _parse_log_level(line: str) -> str:
    upper = line.upper()
    if "ERROR" in upper or "FAILED" in upper:
        return "error"
    if "WARNING" in upper or "WARN" in upper:
        return "warning"
    if "SUCCESS" in upper or "完成" in line or "成功" in line:
        return "success"
    if "DEBUG" in upper:
        return "debug"
    return "info"
