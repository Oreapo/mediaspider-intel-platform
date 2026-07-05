from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends

from ..dependencies import (
    READ_ROLES,
    get_analysis_service,
    get_case_service,
    get_dataset_service,
    get_entity_service,
    get_evidence_service,
    get_signal_service,
    get_task_service,
    require_roles,
)
from ...application.analysis_service import AnalysisService
from ...application.case_service import CaseService
from ...application.dataset_service import DatasetService
from ...application.entity_service import EntityService
from ...application.evidence_service import EvidenceService
from ...application.signal_service import SignalService
from ...application.task_service import CollectionTaskService
from ...domain.models.case import CaseStatus
from ...domain.models.signal import RiskLevel, SignalStatus
from ...domain.models.task import TaskRunStatus


router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("/summary")
def get_dashboard_summary(
    task_service: CollectionTaskService = Depends(get_task_service),
    dataset_service: DatasetService = Depends(get_dataset_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    signal_service: SignalService = Depends(get_signal_service),
    entity_service: EntityService = Depends(get_entity_service),
    case_service: CaseService = Depends(get_case_service),
    evidence_service: EvidenceService = Depends(get_evidence_service),
):
    tasks = task_service.list_tasks()
    runs = task_service.list_runs()
    datasets = dataset_service.list_datasets()
    analysis_jobs = analysis_service.list_jobs()
    signals = signal_service.list_signals()
    entities = entity_service.list_entities()
    relations = entity_service.list_relations()
    cases = case_service.list_cases()
    packets = evidence_service.list_packets()

    signal_risk_levels = Counter(signal.risk_level.value for signal in signals)
    signal_statuses = Counter(signal.status.value for signal in signals)
    case_statuses = Counter(case.status.value for case in cases)
    case_priorities = Counter(case.priority.value for case in cases)
    task_statuses = Counter(task.status.value for task in tasks)
    run_statuses = Counter(run.status.value for run in runs)

    high_risk_levels = {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
    pending_signal_statuses = {SignalStatus.NEW.value, SignalStatus.REVIEWING.value}
    open_case_statuses = {
        CaseStatus.OPEN.value,
        CaseStatus.INVESTIGATING.value,
        CaseStatus.READY_FOR_EVIDENCE.value,
    }
    dataset_by_id = {dataset.id: dataset for dataset in datasets}

    return {
        "summary": {
            "task_count": len(tasks),
            "task_run_count": len(runs),
            "dataset_count": len(datasets),
            "record_count": sum(dataset.record_count for dataset in datasets),
            "analysis_job_count": len(analysis_jobs),
            "signal_count": len(signals),
            "high_risk_signal_count": sum(
                1 for signal in signals if signal.risk_level.value in high_risk_levels
            ),
            "confirmed_signal_count": signal_statuses[SignalStatus.CONFIRMED.value],
            "entity_count": len(entities),
            "relation_count": len(relations),
            "case_count": len(cases),
            "open_case_count": sum(1 for case in cases if case.status.value in open_case_statuses),
            "evidence_packet_count": len(packets),
        },
        "breakdowns": {
            "task_statuses": dict(task_statuses),
            "run_statuses": dict(run_statuses),
            "signal_risk_levels": dict(signal_risk_levels),
            "signal_statuses": dict(signal_statuses),
            "case_statuses": dict(case_statuses),
            "case_priorities": dict(case_priorities),
        },
        "risk_distribution": {
            "platforms": _platform_risk_rows(signals, datasets, entities, dataset_by_id, high_risk_levels),
            "scenarios": _scenario_risk_rows(signals, datasets, cases, dataset_by_id, high_risk_levels),
        },
        "pending": {
            "high_risk_signals": [
                signal.model_dump(mode="json")
                for signal in signals
                if signal.risk_level.value in high_risk_levels
                and signal.status.value in pending_signal_statuses
            ][:5],
            "failed_runs": [
                run.model_dump(mode="json")
                for run in runs
                if run.status == TaskRunStatus.FAILED
            ][:5],
            "ready_cases": [
                case.model_dump(mode="json")
                for case in cases
                if case.status == CaseStatus.READY_FOR_EVIDENCE
            ][:5],
        },
        "latest": {
            "tasks": [task.model_dump(mode="json") for task in tasks[:5]],
            "datasets": [dataset.model_dump(mode="json") for dataset in datasets[:5]],
            "analysis_jobs": [job.model_dump(mode="json") for job in analysis_jobs[:5]],
            "signals": [signal.model_dump(mode="json") for signal in signals[:5]],
            "cases": [case.model_dump(mode="json") for case in cases[:5]],
            "evidence_packets": [packet.model_dump(mode="json") for packet in packets[:5]],
        },
    }


def _platform_risk_rows(signals, datasets, entities, dataset_by_id, high_risk_levels: set[str]) -> list[dict]:
    platforms = {
        dataset.source_platform.value for dataset in datasets
    } | {
        entity.platform.value for entity in entities
    } | {
        dataset_by_id[signal.dataset_id].source_platform.value
        for signal in signals
        if signal.dataset_id in dataset_by_id
    }
    rows = []
    for platform in sorted(platforms):
        platform_signals = [
            signal
            for signal in signals
            if signal.dataset_id in dataset_by_id
            and dataset_by_id[signal.dataset_id].source_platform.value == platform
        ]
        rows.append(
            {
                "key": platform,
                "dataset_count": sum(1 for dataset in datasets if dataset.source_platform.value == platform),
                "signal_count": len(platform_signals),
                "high_risk_signal_count": sum(
                    1 for signal in platform_signals if signal.risk_level.value in high_risk_levels
                ),
                "risk_levels": dict(Counter(signal.risk_level.value for signal in platform_signals)),
                "signal_types": dict(Counter(signal.signal_type.value for signal in platform_signals)),
                "entity_count": sum(1 for entity in entities if entity.platform.value == platform),
            }
        )
    return sorted(rows, key=lambda row: (row["high_risk_signal_count"], row["signal_count"]), reverse=True)


def _scenario_risk_rows(signals, datasets, cases, dataset_by_id, high_risk_levels: set[str]) -> list[dict]:
    scenarios = {
        dataset.scenario_type.value for dataset in datasets if dataset.scenario_type is not None
    } | {
        case.case_type for case in cases
    }
    rows = []
    for scenario in sorted(scenarios):
        scenario_signals = [
            signal
            for signal in signals
            if signal.dataset_id in dataset_by_id
            and dataset_by_id[signal.dataset_id].scenario_type is not None
            and dataset_by_id[signal.dataset_id].scenario_type.value == scenario
        ]
        rows.append(
            {
                "key": scenario,
                "dataset_count": sum(
                    1
                    for dataset in datasets
                    if dataset.scenario_type is not None and dataset.scenario_type.value == scenario
                ),
                "signal_count": len(scenario_signals),
                "high_risk_signal_count": sum(
                    1 for signal in scenario_signals if signal.risk_level.value in high_risk_levels
                ),
                "case_count": sum(1 for case in cases if case.case_type == scenario),
            }
        )
    return sorted(rows, key=lambda row: (row["high_risk_signal_count"], row["case_count"]), reverse=True)
