export interface PlatformFieldOption {
  value: string
  label: string
}

export interface AuthUser {
  username: string
  role: string
  display_name: string
}

export interface LoginResponse {
  token: string
  token_type: string
  user: AuthUser
}

export interface PlatformFieldSchema {
  key: string
  label: string
  group: 'base' | 'input' | 'filters' | 'runtime' | 'storage' | 'analysis' | 'auth'
  control: 'text' | 'textarea' | 'number' | 'select' | 'switch' | 'tags'
  required: boolean
  placeholder: string
  help_text: string
  default: unknown
  visible_for_modes: string[]
  options: PlatformFieldOption[]
}

export interface PlatformTaskModel {
  platform: string
  label: string
  summary: string
  supported_entity_types: string[]
  supported_modes: string[]
  supported_signal_extractors: string[]
  supported_analysis_types: string[]
  task_fields: PlatformFieldSchema[]
}

export interface PlatformProfile {
  id: string
  platform: string
  profile_name: string
  auth_type: string
  credentials_ref: string
  settings_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PlatformProfileDiagnostics {
  ready: boolean
  errors: string[]
  warnings: string[]
  profile: PlatformProfile
  runtime_keys: string[]
}

export interface CollectionTask {
  id: string
  task_name: string
  platform: string
  entity_type: string
  task_mode: string
  scenario_type: string
  status: string
  auth_profile_id: string | null
  task_payload_json: Record<string, unknown>
  filter_payload_json: Record<string, unknown>
  runtime_payload_json: Record<string, unknown>
  storage_profile_json: Record<string, unknown>
  analysis_profile_json: Record<string, unknown>
  notes: string
  last_run_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskRun {
  id: string
  task_id: string
  status: string
  trigger_type: string
  started_at: string | null
  finished_at: string | null
  log_path: string
  result_dataset_id: string | null
  result_dataset_ids: string[]
  error_message: string
  task_snapshot_json: Record<string, unknown>
  run_result_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface TaskRunFailureDiagnosis {
  code: string
  retryable: boolean
  suggestions: string[]
  return_code: number | null
}

export interface SchedulerRunHistoryItem {
  ran_at: string
  status: string
  error?: string
  results: Array<Record<string, unknown>>
  execute_crawler?: boolean
  trigger_type?: 'background' | 'manual' | string
}

export interface SchedulerStatus {
  is_running: boolean
  is_executing: boolean
  queued_runs: number
  active_task_runs: number
  queued_task_runs: number
  queued_task_priority_counts: Record<string, number>
  background_worker_count: number
  max_concurrent_task_runs: number
  task_queue_timeout_seconds: number
  run_leases_supported: boolean
  active_run_leases: number
  task_lease_seconds: number
  lease_owner_id: string
  recovered_task_runs: number
  interval_seconds: number
  execute_crawler: boolean
  run_timeout_seconds: number
  last_result: Record<string, unknown> | null
  last_error: string
  run_history: SchedulerRunHistoryItem[]
}

export interface CrawlerDiagnostics {
  ready: boolean
  media_crawler_root?: string
  output_root?: string
  log_path?: string
  command: string[]
  raw_command?: string[]
  errors: string[]
  warnings: string[]
}

export interface RunLogEntry {
  run: TaskRun
  has_log: boolean
  log_size: number
}

export interface RunLogDetail {
  run: TaskRun
  log_path: string
  line_count: number
  truncated: boolean
  content: string
}

export interface AuditEvent {
  id: string
  action: string
  actor_username: string
  actor_role: string
  target_type: string
  target_id: string
  summary: string
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Signal {
  id: string
  dataset_id: string
  task_run_id: string | null
  signal_type: string
  signal_source: string
  risk_level: string
  risk_score: number
  summary: string
  payload_json: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

export interface SignalDetailPayload {
  signal: Signal
  dataset: Dataset | null
  preview: DatasetPreview
  source_task: CollectionTask | null
  source_run: TaskRun | null
  linked_cases: CaseRecord[]
  linked_case_details: CaseDetail[]
}

export interface RiskEntity {
  id: string
  entity_type: string
  display_name: string
  platform: string
  source_ref: Record<string, unknown>
  risk_score: number
  status: string
  profile_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface EntityRelation {
  id: string
  source_entity_id: string
  target_entity_id: string
  relation_type: string
  confidence: number
  evidence_ref_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface EntityDetail {
  entity: RiskEntity
  signals: Signal[]
  datasets: Dataset[]
  relations: EntityRelation[]
  cases: unknown[]
}

export interface CaseRecord {
  id: string
  case_name: string
  case_type: string
  status: string
  priority: string
  summary: string
  owner: string
  created_at: string
  updated_at: string
}

export interface CaseLink {
  id: string
  case_id: string
  link_type: string
  target_id: string
  label: string
  source_ref_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface CaseNote {
  id: string
  case_id: string
  author: string
  body: string
  note_type: string
  created_at: string
  updated_at: string
}

export interface CaseTimelineItem {
  event_type: string
  event_time: string
  target_type: string
  target_id: string
  title: string
  source_ref: Record<string, unknown>
}

export interface CaseStatusHistoryItem {
  previous_status: string | null
  new_status: string
  changed_at: string
  actor_username: string
  actor_role: string
  source_event_id: string
}

export interface CaseDetail {
  case: CaseRecord
  links: CaseLink[]
  notes: CaseNote[]
  objects: {
    datasets: Dataset[]
    signals: Signal[]
    entities: RiskEntity[]
    analysis_outputs: AnalysisOutput[]
    evidence_packets: EvidencePacket[]
  }
  timeline: CaseTimelineItem[]
  status_history: CaseStatusHistoryItem[]
  audit_events: AuditEvent[]
}

export interface EvidencePacket {
  id: string
  case_id: string
  packet_name: string
  storage_uri: string
  manifest_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Report {
  id: string
  case_id: string
  report_name: string
  report_type: string
  status: string
  storage_uri: string
  content_markdown: string
  summary_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface NotificationRule {
  id: string
  rule_name: string
  enabled: boolean
  event_type: string
  risk_level_threshold: string
  scenario_types: string[]
  platforms: string[]
  channels: string[]
  cron_expr: string
  cooldown_minutes: number
  channel_config_json: Record<string, unknown>
  last_executed_at: string | null
  created_at: string
  updated_at: string
}

export interface NotificationDelivery {
  id: string
  rule_id: string
  target_type: string
  target_id: string
  channel: string
  status: string
  payload_json: Record<string, unknown>
  error_message: string
  retry_count: number
  last_attempt_at: string | null
  created_at: string
  updated_at: string
}

export interface NotificationInboxItem {
  id: string
  rule_id: string
  rule_name: string
  target_type: string
  target_id: string
  status: string
  read: boolean
  read_at: string | null
  created_at: string
  event_count: number
  title: string
  summary: string
  payload_json: Record<string, unknown>
}

export interface Dataset {
  id: string
  dataset_name: string
  dataset_type: string
  source_platform: string
  source_task_id: string | null
  source_run_id: string | null
  scenario_type: string | null
  record_count: number
  storage_uri: string
  schema_version: string
  snapshot_time: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface DatasetPreview {
  columns: string[]
  rows: string[][]
  mode: string
  total: number
}

export interface AnalysisJob {
  id: string
  dataset_id: string
  analysis_scope: string
  analysis_type: string
  status: string
  parameters_json: Record<string, unknown>
  started_at: string | null
  finished_at: string | null
  error_message: string
  created_at: string
  updated_at: string
}

export interface AnalysisOutput {
  id: string
  analysis_job_id: string
  output_type: string
  title: string
  summary: string
  payload_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DashboardSummary {
  summary: {
    task_count: number
    task_run_count: number
    dataset_count: number
    record_count: number
    analysis_job_count: number
    signal_count: number
    high_risk_signal_count: number
    confirmed_signal_count: number
    entity_count: number
    relation_count: number
    case_count: number
    open_case_count: number
    evidence_packet_count: number
  }
  breakdowns: {
    task_statuses: Record<string, number>
    run_statuses: Record<string, number>
    signal_risk_levels: Record<string, number>
    signal_statuses: Record<string, number>
    case_statuses: Record<string, number>
    case_priorities: Record<string, number>
  }
  risk_distribution: {
    platforms: Array<{
      key: string
      dataset_count: number
      signal_count: number
      high_risk_signal_count: number
      risk_levels: Record<string, number>
      signal_types: Record<string, number>
      entity_count: number
    }>
    scenarios: Array<{
      key: string
      dataset_count: number
      signal_count: number
      high_risk_signal_count: number
      case_count: number
    }>
  }
  pending: {
    high_risk_signals: Signal[]
    failed_runs: TaskRun[]
    ready_cases: CaseRecord[]
  }
  latest: {
    tasks: CollectionTask[]
    datasets: Dataset[]
    analysis_jobs: AnalysisJob[]
    signals: Signal[]
    cases: CaseRecord[]
    evidence_packets: EvidencePacket[]
  }
}
