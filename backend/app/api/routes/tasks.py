from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_task_service
from ..schemas.task import CollectionTaskCreateRequest, CollectionTaskUpdateRequest, TaskRunStartRequest
from ...application.task_service import CollectionTaskService
from ...domain.models.task import TaskStatus


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(service: CollectionTaskService = Depends(get_task_service)):
    return {"tasks": [task.model_dump(mode="json") for task in service.list_tasks()]}


@router.get("/{task_id}")
def get_task(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task.model_dump(mode="json")}


@router.post("")
def create_task(
    payload: CollectionTaskCreateRequest,
    service: CollectionTaskService = Depends(get_task_service),
):
    task = service.create_task(payload)
    return {"message": "Task created", "task": task.model_dump(mode="json")}


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    payload: CollectionTaskUpdateRequest,
    service: CollectionTaskService = Depends(get_task_service),
):
    try:
        task = service.update_task(task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Task updated", "task": task.model_dump(mode="json")}


@router.delete("/{task_id}")
def delete_task(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    deleted = service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}


@router.post("/{task_id}/enable")
def enable_task(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    try:
        task = service.set_task_status(task_id, TaskStatus.ENABLED)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Task enabled", "task": task.model_dump(mode="json")}


@router.post("/{task_id}/disable")
def disable_task(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    try:
        task = service.set_task_status(task_id, TaskStatus.DISABLED)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Task disabled", "task": task.model_dump(mode="json")}


@router.get("/{task_id}/runs")
def list_task_runs(task_id: str, service: CollectionTaskService = Depends(get_task_service)):
    if service.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"runs": [run.model_dump(mode="json") for run in service.list_runs(task_id)]}


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


@router.post("/{task_id}/runs")
def start_task_run(
    task_id: str,
    payload: TaskRunStartRequest | None = None,
    service: CollectionTaskService = Depends(get_task_service),
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
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"message": "Task run completed" if start_payload.execute_crawler else "Task run started", "run": run.model_dump(mode="json")}
