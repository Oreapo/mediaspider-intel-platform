from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CollectionTaskTable(Base):
    __tablename__ = "collection_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    task_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_profile_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    task_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    filter_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    storage_profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class TaskRunTable(Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")
    log_path: Mapped[str] = mapped_column(String(255), default="")
    result_dataset_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_dataset_ids: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str] = mapped_column(Text, default="")
    task_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    run_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class DatasetTable(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(120), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scenario_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_uri: Mapped[str] = mapped_column(String(255), default="")
    schema_version: Mapped[str] = mapped_column(String(32), default="v1")
    snapshot_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class AnalysisJobTable(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analysis_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class SignalTable(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    task_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signal_source: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class RiskEntityTable(Base):
    __tablename__ = "risk_entities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_ref: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class EntityRelationTable(Base):
    __tablename__ = "entity_relations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_entity_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_entity_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    evidence_ref_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class CaseTable(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_name: Mapped[str] = mapped_column(String(160), nullable=False)
    case_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class CaseLinkTable(Base):
    __tablename__ = "case_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    source_ref_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class CaseNoteTable(Base):
    __tablename__ = "case_notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(80), default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(80), default="investigation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class EvidencePacketTable(Base):
    __tablename__ = "evidence_packets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    packet_name: Mapped[str] = mapped_column(String(160), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class ReportTable(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    report_name: Mapped[str] = mapped_column(String(160), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    storage_uri: Mapped[str] = mapped_column(String(255), default="")
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class NotificationRuleTable(Base):
    __tablename__ = "notification_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    risk_level_threshold: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario_types: Mapped[list] = mapped_column(JSON, default=list)
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    cron_expr: Mapped[str] = mapped_column(String(80), default="*/30 * * * *")
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    channel_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class NotificationDeliveryTable(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
