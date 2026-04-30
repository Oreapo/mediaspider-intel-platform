from __future__ import annotations

from .container import AppContainer, container as _container
from ...application.analysis_service import AnalysisService
from ...application.case_service import CaseService
from ...application.dataset_service import DatasetService
from ...application.entity_service import EntityService
from ...application.evidence_service import EvidenceService
from ...application.log_service import LogService
from ...application.notification_service import NotificationService
from ...application.signal_service import SignalService
from ...application.task_service import CollectionTaskService


container = _container


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
]
