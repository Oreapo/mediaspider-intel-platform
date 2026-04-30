export interface PlatformFieldOption {
  value: string
  label: string
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

export interface CaseDetail {
  case: CaseRecord
  links: CaseLink[]
  notes: CaseNote[]
  objects: {
    datasets: Dataset[]
    signals: Signal[]
    entities: RiskEntity[]
    analysis_outputs: AnalysisOutput[]
    evidence_packets: unknown[]
  }
  timeline: CaseTimelineItem[]
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
  created_at: string
  updated_at: string
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
