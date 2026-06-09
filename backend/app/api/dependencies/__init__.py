from __future__ import annotations

from .container import AppContainer, container as _container
from ...application.analysis_service import AnalysisService
from ...application.audit_service import AuditService
from ...application.auth_service import AuthService, AuthUser
from ...application.case_service import CaseService
from ...application.dataset_service import DatasetService
from ...application.entity_service import EntityService
from ...application.evidence_service import EvidenceService
from ...application.log_service import LogService
from ...application.notification_service import NotificationService
from ...application.platform_profile_service import PlatformProfileService
from ...application.report_service import ReportService
from ...application.scheduler_service import BackgroundScheduler
from ...application.signal_service import SignalService
from ...application.task_service import CollectionTaskService
from fastapi import Depends, Header, HTTPException, Query


container = _container

READ_ROLES = ("admin", "analyst", "operator", "viewer")
ANALYST_ROLES = ("admin", "analyst")
OPERATOR_ROLES = ("admin", "operator")
WORKFLOW_ROLES = ("admin", "analyst", "operator")


def set_container(new_container: AppContainer) -> None:
    global container
    container = new_container


def get_task_service() -> CollectionTaskService:
    return container.task_service


def get_dataset_service() -> DatasetService:
    return container.dataset_service


def get_analysis_service() -> AnalysisService:
    return container.analysis_service


def get_signal_service() -> SignalService:
    return container.signal_service


def get_entity_service() -> EntityService:
    return container.entity_service


def get_case_service() -> CaseService:
    return container.case_service


def get_evidence_service() -> EvidenceService:
    return container.evidence_service


def get_notification_service() -> NotificationService:
    return container.notification_service


def get_log_service() -> LogService:
    return container.log_service


def get_report_service() -> ReportService:
    return container.report_service


def get_platform_profile_service() -> PlatformProfileService:
    return container.platform_profile_service


def get_auth_service() -> AuthService:
    return container.auth_service


def get_audit_service() -> AuditService:
    return container.audit_service


def get_scheduler_service() -> BackgroundScheduler:
    return container.scheduler_service


def require_user(
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
    service: AuthService = Depends(get_auth_service),
) -> AuthUser:
    token = _bearer_token(authorization) or access_token
    if not service.auth_required and not token:
        return service.anonymous_user()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return service.verify_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def require_roles(*roles: str):
    def dependency(user: AuthUser = Depends(require_user), service: AuthService = Depends(get_auth_service)) -> AuthUser:
        if not service.user_has_role(user, roles):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


__all__ = [
    "container",
    "set_container",
    "get_task_service",
    "get_dataset_service",
    "get_analysis_service",
    "get_signal_service",
    "get_entity_service",
    "get_case_service",
    "get_evidence_service",
    "get_notification_service",
    "get_log_service",
    "get_report_service",
    "get_platform_profile_service",
    "get_auth_service",
    "get_audit_service",
    "get_scheduler_service",
    "require_user",
    "require_roles",
    "READ_ROLES",
    "ANALYST_ROLES",
    "OPERATOR_ROLES",
    "WORKFLOW_ROLES",
]
