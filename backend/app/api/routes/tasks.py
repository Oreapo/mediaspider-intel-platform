from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import OPERATOR_ROLES, READ_ROLES, get_audit_service, get_scheduler_service, get_task_service, require_roles
from ..schemas.task import CollectionTaskCreateRequest, CollectionTaskUpdateRequest, ScheduledTaskRunRequest, TaskRunStartRequest
from ...application.audit_service import AuditService
from ...application.auth_service import AuthUser
from ...application.task_service import CollectionTaskService
from ...application.scheduler_service import BackgroundScheduler
from ...domain.models.platform import PlatformKey
from ...domain.models.task import EntityType, ScenarioType, TaskMode, TaskStatus


router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("")
def list_tasks(
    platform: PlatformKey | None = None,
    status: TaskStatus | None = None,
    task_mode: TaskMode | None = None,
    entity_type: EntityType | None = None,
    scenario_type: ScenarioType | None = None,
    q: str = "",
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CollectionTaskService = Depends(get_task_service),
):
    tasks, total = service.list_tasks_page(
        platform=platform,
        status=status,
        task_mode=task_mode,
        entity_type=entity_type,
        scenario_type=scenario_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {"tasks": [task.model_dump(mode="json") for task in tasks], "total": total}


@router.get("/{task_id}")
def get_task(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task.model_dump(mode="json")}


@router.post("", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def create_task(
    payload: CollectionTaskCreateRequest,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    task = service.create_task(payload)
    audit_service.record(
        action="task.create",
        actor=actor,
        target_type="task",
        target_id=task.id,
        summary=f"创建采集任务：{task.task_name}",
        metadata_json={"platform": task.platform.value, "scenario_type": task.scenario_type.value},
    )
    return {"message": "Task created", "task": task.model_dump(mode="json")}


@router.post("/run-scheduled", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
async def run_scheduled_tasks(
    payload: ScheduledTaskRunRequest | None = None,
    scheduler: BackgroundScheduler = Depends(get_scheduler_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    start_payload = payload or ScheduledTaskRunRequest()
    try:
        now = datetime.fromisoformat(start_payload.now) if start_payload.now else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid now datetime") from exc
    try:
        result = await scheduler.run_once(
            now=now,
            execute_crawler=start_payload.execute_crawler,
            trigger_type="manual",
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    audit_service.record(
        action="task.run_scheduled",
        actor=actor,
        target_type="scheduler",
        target_id="collection_tasks",
        summary=f"手动触发定时任务扫描，命中 {len(result.get('results', []))} 条结果",
        metadata_json={
            "now": start_payload.now,
            "execute_crawler": start_payload.execute_crawler,
            "result_count": len(result.get("results", [])),
        },
    )
    return result


@router.get("/scheduler/status")
def get_scheduler_status(
    scheduler: BackgroundScheduler = Depends(get_scheduler_service),
    service: CollectionTaskService = Depends(get_task_service),
):
    return {
        "is_running": scheduler.is_running,
        "is_executing": scheduler.is_executing,
        "queued_runs": scheduler.queued_runs,
        "active_task_runs": service.active_task_runs,
        "queued_task_runs": service.queued_task_runs,
        "max_concurrent_task_runs": service.max_concurrent_runs,
        "task_queue_timeout_seconds": service.queue_timeout_seconds,
        "recovered_task_runs": service.recovered_task_runs,
        "interval_seconds": scheduler.interval_seconds,
        "execute_crawler": scheduler.execute_crawler,
        "run_timeout_seconds": scheduler.run_timeout_seconds,
        "last_result": scheduler.last_result,
        "last_error": scheduler.last_error,
        "run_history": scheduler.run_history,
    }


@router.patch("/{task_id}", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def update_task(
    task_id: str,
    payload: CollectionTaskUpdateRequest,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    try:
        task = service.update_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="task.update",
        actor=actor,
        target_type="task",
        target_id=task.id,
        summary=f"更新采集任务：{task.task_name}",
        metadata_json={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    return {"message": "Task updated", "task": task.model_dump(mode="json")}


@router.delete("/{task_id}", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def delete_task(
    task_id: str,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    task = service.get_task(task_id)
    deleted = service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    audit_service.record(
        action="task.delete",
        actor=actor,
        target_type="task",
        target_id=task_id,
        summary=f"删除采集任务：{task.task_name if task else task_id}",
        metadata_json={"task_name": task.task_name if task else ""},
    )
    return {"message": "Task deleted"}


@router.post("/{task_id}/enable", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def enable_task(
    task_id: str,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    try:
        task = service.set_task_status(task_id, TaskStatus.ENABLED)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="task.enable",
        actor=actor,
        target_type="task",
        target_id=task.id,
        summary=f"启用采集任务：{task.task_name}",
    )
    return {"message": "Task enabled", "task": task.model_dump(mode="json")}


@router.post("/{task_id}/disable", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def disable_task(
    task_id: str,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    try:
        task = service.set_task_status(task_id, TaskStatus.DISABLED)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="task.disable",
        actor=actor,
        target_type="task",
        target_id=task.id,
        summary=f"停用采集任务：{task.task_name}",
    )
    return {"message": "Task disabled", "task": task.model_dump(mode="json")}


@router.get("/{task_id}/runs")
def list_task_runs(
    task_id: str,
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CollectionTaskService = Depends(get_task_service),
):
    if service.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    result = service.list_runs_page(task_id, limit=limit, offset=offset)
    return {
        "runs": [run.model_dump(mode="json") for run in result["runs"]],
        "total": result["total"],
        "status_counts": result["status_counts"],
    }


@router.get("/{task_id}/crawler-diagnostics")
def get_crawler_diagnostics(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    try:
        return {"diagnostics": service.diagnose_crawler(task_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/runs/{run_id}")
def get_task_run(
    task_id: str,
    run_id: str,
    service: CollectionTaskService = Depends(get_task_service),
):
    run = service.get_run(run_id)
    if run is None or run.task_id != task_id:
        raise HTTPException(status_code=404, detail="Task run not found")
    return {"run": run.model_dump(mode="json")}


@router.post(
    "/{task_id}/runs/{run_id}/cancel",
    dependencies=[Depends(require_roles(*OPERATOR_ROLES))],
)
def cancel_task_run(
    task_id: str,
    run_id: str,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    try:
        run = service.cancel_run(task_id, run_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    audit_service.record(
        action="task.run_cancel",
        actor=actor,
        target_type="task_run",
        target_id=run.id,
        summary=f"取消排队中的采集任务运行：{run.id}",
        metadata_json={"task_id": task_id, "status": run.status.value},
    )
    return {"message": "Task run cancelled", "run": run.model_dump(mode="json")}


@router.post("/{task_id}/runs", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def start_task_run(
    task_id: str,
    payload: TaskRunStartRequest | None = None,
    service: CollectionTaskService = Depends(get_task_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*OPERATOR_ROLES)),
):
    start_payload = payload or TaskRunStartRequest()
    try:
        run = service.start_run(
            task_id,
            trigger_type=start_payload.trigger_type,
            execute_crawler=start_payload.execute_crawler,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered_detail = detail.lower()
        if "not found" in lowered_detail:
            status_code = 404
        elif "already has active run" in lowered_detail:
            status_code = 409
        elif "queue timed out" in lowered_detail:
            status_code = 503
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    audit_service.record(
        action="task.run",
        actor=actor,
        target_type="task_run",
        target_id=run.id,
        summary=f"触发采集任务运行：{task_id}",
        metadata_json={
            "task_id": task_id,
            "trigger_type": start_payload.trigger_type,
            "execute_crawler": start_payload.execute_crawler,
            "status": run.status.value,
        },
    )
    return {"message": "Task run completed" if start_payload.execute_crawler else "Task run started", "run": run.model_dump(mode="json")}
