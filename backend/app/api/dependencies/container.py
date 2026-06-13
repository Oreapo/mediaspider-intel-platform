from __future__ import annotations

import os
from pathlib import Path

from ...application.analysis_service import AnalysisService
from ...application.audit_service import AuditService
from ...application.auth_service import AuthService
from ...application.case_service import CaseService
from ...application.crawler_runner import CrawlerRunner, MediaCrawlerProcessRunner
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
from ...infrastructure.persistence.json_analysis_repository import JsonAnalysisRepository
from ...infrastructure.persistence.json_audit_repository import JsonAuditRepository
from ...infrastructure.persistence.json_case_repository import JsonCaseRepository
from ...infrastructure.persistence.json_dataset_repository import JsonDatasetRepository
from ...infrastructure.persistence.json_entity_repository import JsonEntityRepository
from ...infrastructure.persistence.json_evidence_repository import JsonEvidenceRepository
from ...infrastructure.persistence.json_notification_repository import JsonNotificationRepository
from ...infrastructure.persistence.json_platform_profile_repository import JsonPlatformProfileRepository
from ...infrastructure.persistence.json_report_repository import JsonReportRepository
from ...infrastructure.persistence.json_signal_repository import JsonSignalRepository
from ...infrastructure.persistence.json_task_repository import JsonCollectionTaskRepository
from ...infrastructure.persistence.sqlite_analysis_repository import SQLiteAnalysisRepository
from ...infrastructure.persistence.sqlite_dataset_repository import SQLiteDatasetRepository
from ...infrastructure.persistence.sqlite_audit_repository import SQLiteAuditRepository
from ...infrastructure.persistence.sqlite_case_repository import SQLiteCaseRepository
from ...infrastructure.persistence.sqlite_entity_repository import SQLiteEntityRepository
from ...infrastructure.persistence.sqlite_evidence_repository import SQLiteEvidenceRepository
from ...infrastructure.persistence.sqlite_notification_repository import SQLiteNotificationRepository
from ...infrastructure.persistence.sqlite_platform_profile_repository import SQLitePlatformProfileRepository
from ...infrastructure.persistence.sqlite_report_repository import SQLiteReportRepository
from ...infrastructure.persistence.sqlite_signal_repository import SQLiteSignalRepository
from ...infrastructure.persistence.sqlite_task_repository import SQLiteCollectionTaskRepository


class AppContainer:
    def __init__(
        self,
        root_dir: Path,
        crawler_runner: CrawlerRunner | None = None,
        media_crawler_root: Path | None = None,
    ):
        self.root_dir = root_dir
        self.storage_dir = Path(os.getenv("MEDIASPIDER_STORAGE_DIR", str(root_dir / "storage")))
        self._task_repository = self._build_task_repository()
        self._dataset_repository = self._build_dataset_repository()
        self._analysis_repository = self._build_analysis_repository()
        self._signal_repository = self._build_signal_repository()
        self._entity_repository = self._build_entity_repository()
        self._case_repository = self._build_case_repository()
        self._evidence_repository = self._build_evidence_repository()
        self._notification_repository = self._build_notification_repository()
        self._report_repository = self._build_report_repository()
        self._platform_profile_repository = self._build_platform_profile_repository()
        self._audit_repository = self._build_audit_repository()
        self._auth_service = AuthService()
        self._audit_service = AuditService(self._audit_repository)
        self._platform_profile_service = PlatformProfileService(self._platform_profile_repository)
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
            self._platform_profile_service.resolve_runtime_auth,
            max_concurrent_runs=int(os.getenv("MEDIASPIDER_TASK_MAX_CONCURRENT_RUNS", "1")),
            queue_timeout_seconds=float(os.getenv("MEDIASPIDER_TASK_QUEUE_TIMEOUT_SECONDS", "300")),
            recover_interrupted_runs=os.getenv(
                "MEDIASPIDER_TASK_RECOVER_INTERRUPTED_RUNS",
                "true",
            ).lower() == "true",
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
        self._scheduler_service = BackgroundScheduler(
            self._task_service,
            self._audit_service,
            interval_seconds=int(os.getenv("MEDIASPIDER_SCHEDULER_INTERVAL_SECONDS", "60")),
            execute_crawler=os.getenv("MEDIASPIDER_SCHEDULER_EXECUTE_CRAWLER", "true").lower() == "true",
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

    @property
    def platform_profile_service(self) -> PlatformProfileService:
        return self._platform_profile_service

    @property
    def auth_service(self) -> AuthService:
        return self._auth_service

    @property
    def audit_service(self) -> AuditService:
        return self._audit_service

    @property
    def scheduler_service(self) -> BackgroundScheduler:
        return self._scheduler_service

    def _default_media_crawler_root(self) -> Path:
        configured_root = os.getenv("MEDIASPIDER_MEDIA_CRAWLER_ROOT")
        if configured_root:
            return Path(configured_root)
        if self.root_dir.name == "mediaspider-intel-platform" and self.root_dir.parent.name == "products":
            return self.root_dir.parent.parent
        return self.root_dir

    def _uses_sqlite(self, repository_name: str) -> bool:
        repository_mode = os.getenv("MEDIASPIDER_REPOSITORY_MODE", "").lower()
        if repository_mode == "sqlite":
            return True
        return os.getenv(repository_name, "").lower() == "sqlite"

    def _sqlite_path(self) -> Path:
        return Path(
            os.getenv(
                "MEDIASPIDER_SQLITE_PATH",
                str(self.storage_dir / "mediaspider-intel.sqlite3"),
            )
        )

    def _build_dataset_repository(self):
        if self._uses_sqlite("MEDIASPIDER_DATASET_REPOSITORY"):
            return SQLiteDatasetRepository(self._sqlite_path())
        return JsonDatasetRepository(self.storage_dir / "datasets.json")

    def _build_task_repository(self):
        if self._uses_sqlite("MEDIASPIDER_TASK_REPOSITORY"):
            return SQLiteCollectionTaskRepository(self._sqlite_path())
        return JsonCollectionTaskRepository(
            self.storage_dir / "collection_tasks.json",
            self.storage_dir / "task_runs.json",
        )

    def _build_analysis_repository(self):
        if self._uses_sqlite("MEDIASPIDER_ANALYSIS_REPOSITORY"):
            return SQLiteAnalysisRepository(self._sqlite_path())
        return JsonAnalysisRepository(
            self.storage_dir / "analysis_jobs.json",
            self.storage_dir / "analysis_outputs.json",
        )

    def _build_signal_repository(self):
        if self._uses_sqlite("MEDIASPIDER_SIGNAL_REPOSITORY"):
            return SQLiteSignalRepository(self._sqlite_path())
        return JsonSignalRepository(self.storage_dir / "signals.json")

    def _build_entity_repository(self):
        if self._uses_sqlite("MEDIASPIDER_ENTITY_REPOSITORY"):
            return SQLiteEntityRepository(self._sqlite_path())
        return JsonEntityRepository(
            self.storage_dir / "risk_entities.json",
            self.storage_dir / "entity_relations.json",
        )

    def _build_case_repository(self):
        if self._uses_sqlite("MEDIASPIDER_CASE_REPOSITORY"):
            return SQLiteCaseRepository(self._sqlite_path())
        return JsonCaseRepository(
            self.storage_dir / "cases.json",
            self.storage_dir / "case_links.json",
            self.storage_dir / "case_notes.json",
        )

    def _build_evidence_repository(self):
        if self._uses_sqlite("MEDIASPIDER_EVIDENCE_REPOSITORY"):
            return SQLiteEvidenceRepository(self._sqlite_path())
        return JsonEvidenceRepository(self.storage_dir / "evidence_packets.json")

    def _build_report_repository(self):
        if self._uses_sqlite("MEDIASPIDER_REPORT_REPOSITORY"):
            return SQLiteReportRepository(self._sqlite_path())
        return JsonReportRepository(self.storage_dir / "reports.json")

    def _build_notification_repository(self):
        if self._uses_sqlite("MEDIASPIDER_NOTIFICATION_REPOSITORY"):
            return SQLiteNotificationRepository(self._sqlite_path())
        return JsonNotificationRepository(
            self.storage_dir / "notification_rules.json",
            self.storage_dir / "notification_deliveries.json",
        )

    def _build_platform_profile_repository(self):
        if self._uses_sqlite("MEDIASPIDER_PLATFORM_PROFILE_REPOSITORY"):
            return SQLitePlatformProfileRepository(self._sqlite_path())
        return JsonPlatformProfileRepository(self.storage_dir / "platform_profiles.json")

    def _build_audit_repository(self):
        if self._uses_sqlite("MEDIASPIDER_AUDIT_REPOSITORY"):
            return SQLiteAuditRepository(self._sqlite_path())
        return JsonAuditRepository(self.storage_dir / "audit_events.json")


container = AppContainer(Path(__file__).resolve().parents[3])
