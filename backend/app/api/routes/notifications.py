from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_notification_service
from ..schemas.notification import (
    NotificationDigestRunRequest,
    NotificationRuleCreateRequest,
    NotificationRuleUpdateRequest,
)
from ...application.notification_service import NotificationService


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/rules")
def list_notification_rules(service: NotificationService = Depends(get_notification_service)):
    return {"rules": [rule.model_dump(mode="json") for rule in service.list_rules()]}


@router.post("/rules")
def create_notification_rule(
    payload: NotificationRuleCreateRequest,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        rule = service.create_rule(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Notification rule created", "rule": rule.model_dump(mode="json")}


@router.get("/rules/{rule_id}")
def get_notification_rule(rule_id: str, service: NotificationService = Depends(get_notification_service)):
    rule = service.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    return {"rule": rule.model_dump(mode="json")}


@router.patch("/rules/{rule_id}")
def update_notification_rule(
    rule_id: str,
    payload: NotificationRuleUpdateRequest,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        rule = service.update_rule(rule_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"message": "Notification rule updated", "rule": rule.model_dump(mode="json")}


@router.delete("/rules/{rule_id}")
def delete_notification_rule(rule_id: str, service: NotificationService = Depends(get_notification_service)):
    deleted = service.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    return {"message": "Notification rule deleted"}


@router.get("/deliveries")
def list_notification_deliveries(service: NotificationService = Depends(get_notification_service)):
    return {"deliveries": [delivery.model_dump(mode="json") for delivery in service.list_deliveries()]}


@router.post("/run-scheduled")
def run_scheduled_notifications(
    payload: NotificationDigestRunRequest,
    service: NotificationService = Depends(get_notification_service),
):
    now = datetime.fromisoformat(payload.now) if payload.now else None
    return service.run_scheduled_digests(now=now)
