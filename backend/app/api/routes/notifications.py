from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import OPERATOR_ROLES, READ_ROLES, WORKFLOW_ROLES, get_notification_service, require_roles
from ..schemas.notification import (
    NotificationDigestRunRequest,
    NotificationInboxUpdateRequest,
    NotificationRuleCreateRequest,
    NotificationRuleUpdateRequest,
)
from ...application.notification_service import NotificationService
from ...domain.models.notification import NotificationChannel, NotificationDeliveryStatus


router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("/rules")
def list_notification_rules(service: NotificationService = Depends(get_notification_service)):
    return {"rules": [rule.model_dump(mode="json") for rule in service.list_rules()]}


@router.post("/rules", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
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


@router.patch("/rules/{rule_id}", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
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


@router.delete("/rules/{rule_id}", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def delete_notification_rule(rule_id: str, service: NotificationService = Depends(get_notification_service)):
    deleted = service.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification rule not found")
    return {"message": "Notification rule deleted"}


@router.get("/deliveries")
def list_notification_deliveries(
    rule_id: str | None = None,
    status: NotificationDeliveryStatus | None = None,
    channel: NotificationChannel | None = None,
    target_type: str = "",
    q: str = "",
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: NotificationService = Depends(get_notification_service),
):
    deliveries, total = service.search_delivery_page(
        rule_id=rule_id,
        status=status,
        channel=channel,
        target_type=target_type,
        query=q,
        limit=limit,
        offset=offset,
    )
    return {
        "deliveries": [delivery.model_dump(mode="json") for delivery in deliveries],
        "total": total,
    }


@router.post("/deliveries/{delivery_id}/retry", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def retry_notification_delivery(
    delivery_id: str,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        delivery = service.retry_delivery(delivery_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"message": "Notification delivery retried", "delivery": delivery.model_dump(mode="json")}


@router.get("/inbox")
def list_notification_inbox(
    unread_only: bool = False,
    q: str = "",
    limit: int | None = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: NotificationService = Depends(get_notification_service),
):
    return service.list_inbox(unread_only=unread_only, query=q, limit=limit, offset=offset)


@router.patch("/inbox/{delivery_id}", dependencies=[Depends(require_roles(*WORKFLOW_ROLES))])
def update_notification_inbox_item(
    delivery_id: str,
    payload: NotificationInboxUpdateRequest,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        return {"item": service.update_inbox_item(delivery_id, read=payload.read)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/inbox/mark-all-read", dependencies=[Depends(require_roles(*WORKFLOW_ROLES))])
def mark_all_notification_inbox_read(service: NotificationService = Depends(get_notification_service)):
    return service.mark_all_inbox_read()


@router.post("/run-scheduled", dependencies=[Depends(require_roles(*OPERATOR_ROLES))])
def run_scheduled_notifications(
    payload: NotificationDigestRunRequest,
    service: NotificationService = Depends(get_notification_service),
):
    now = datetime.fromisoformat(payload.now) if payload.now else None
    return service.run_scheduled_digests(now=now)
