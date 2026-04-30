from __future__ import annotations

from pathlib import Path

from ...application.analysis_service import AnalysisService
from ...application.case_service import CaseService
from ...application.crawler_runner import CrawlerRunner, MediaCrawlerProcessRunner
from ...application.dataset_service import DatasetService
from ...application.entity_service import EntityService
from ...application.evidence_service import EvidenceService
from ...application.log_service import LogService
from ...application.notification_service import NotificationService
from ...application.report_service import ReportService
from ...application.signal_service import SignalService
from ...application.task_service import CollectionTaskService
from ...infrastructure.persistence.json_analysis_repository import JsonAnalysisRepository
from ...infrastructure.persistence.json_case_repository import JsonCaseRepository
from ...infrastructure.persistence.json_dataset_repository import JsonDatasetRepository
from ...infrastructure.persistence.json_entity_repository import JsonEntityRepository
from ...infrastructure.persistence.json_evidence_repository import JsonEvidenceRepository
from ...infrastructure.persistence.json_notification_repository import JsonNotificationRepository
from ...infrastructure.persistence.json_report_repository import JsonReportRepository
from ...infrastructure.persistence.json_signal_repository import JsonSignalRepository
from ...infrastructure.persistence.json_task_repository import JsonCollectionTaskRepository


class AppContainer:
    def __init__(
        self,
        root_dir: Path,
        crawler_runner: CrawlerRunner | None = None,
        media_crawler_root: Path | None = None,
    ):
        self.root_dir = root_dir
        self.storage_dir = root_dir / "storage"
        self._task_repository = JsonCollectionTaskRepository(
            self.storage_dir / "collection_tasks.json",
            self.storage_dir / "task_runs.json",
        )
        self._dataset_repository = JsonDatasetRepository(
            self.storage_dir / "datasets.json"
        )
        self._analysis_repository = JsonAnalysisRepository(
            self.storage_dir / "analysis_jobs.json",
            self.storage_dir / "analysis_outputs.json",
        )
        self._signal_repository = JsonSignalRepository(
            self.storage_dir / "signals.json"
        )
        self._entity_repository = JsonEntityRepository(
            self.storage_dir / "risk_entities.json",
            self.storage_dir / "entity_relations.json",
        )
        self._case_repository = JsonCaseRepository(
            self.storage_dir / "cases.json",
            self.storage_dir / "case_links.json",
            self.storage_dir / "case_notes.json",
        )
        self._evidence_repository = JsonEvidenceRepository(
            self.storage_dir / "evidence_packets.json"
        )
        self._notification_repository = JsonNotificationRepository(
            self.storage_dir / "notification_rules.json",
            self.storage_dir / "notification_deliveries.json",
        )
        self._report_repository = JsonReportRepository(
            self.storage_dir / "reports.json"
        )
        self._dataset_service = DatasetService(
            self._dataset_repository,
            self.storage_dir / "dataset_files",
        )
        self._crawler_runner = crawler_runner or MediaCrawlerProcessRunner(
            media_crawler_root=media_crawler_root or self._default_media_crawler_root(),
            storage_root=self.storage_dir,
        )
        self._task_service = CollectionTaskService(
            self._task_repository,
            self._dataset_service,
            self._crawler_runner,
        )
        self._analysis_service = AnalysisService(
            self._analysis_repository,
            self._dataset_service,
        )
        self._signal_service = SignalService(
            self._signal_repository,
            self._dataset_service,
        )
        self._entity_service = EntityService(
            self._entity_repository,
            self._signal_service,
            self._dataset_service,
        )
        self._case_service = CaseService(
            self._case_repository,
            self._dataset_service,
            self._signal_service,
            self._entity_service,
            self._analysis_service,
        )
        self._evidence_service = EvidenceService(
            self._evidence_repository,
            self._case_service,
            self.storage_dir / "evidence_packet_files",
        )
        self._case_service.set_evidence_packet_resolver(self._evidence_service.get_packet)
        self._notification_service = NotificationService(
            self._notification_repository,
            self._signal_service,
            self._case_service,
            self._evidence_service,
            self._dataset_service,
        )
        self._log_service = LogService(self._task_service, self.storage_dir)
        self._report_service = ReportService(
            self._report_repository,
            self._case_service,
            self.storage_dir / "report_files",
        )

    @property
    def task_service(self) -> CollectionTaskService:
        return self._task_service

    @property
    def dataset_service(self) -> DatasetService:
        return self._dataset_service

    @property
    def analysis_service(self) -> AnalysisService:
        return self._analysis_service

    @property
    def signal_service(self) -> SignalService:
        return self._signal_service

    @property
    def entity_service(self) -> EntityService:
        return self._entity_service

    @property
    def case_service(self) -> CaseService:
        return self._case_service

    @property
    def evidence_service(self) -> EvidenceService:
        return self._evidence_service

    @property
    def notification_service(self) -> NotificationService:
        return self._notification_service

    @property
    def log_service(self) -> LogService:
        return self._log_service

    @property
    def report_service(self) -> ReportService:
        return self._report_service

    def _default_media_crawler_root(self) -> Path:
        if self.root_dir.name == "mediaspider-intel-platform" and self.root_dir.parent.name == "products":
            return self.root_dir.parent.parent
        return self.root_dir


container = AppContainer(Path(__file__).resolve().parents[3])
