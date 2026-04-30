# Requirements

## Product Scope

`MediaSpider Intelligence Platform` is a web platform for anti-black-gray intelligence collection and investigation.

The platform must support the full workflow:

1. Configure multi-platform collection tasks.
2. Run controlled collection jobs.
3. Store raw and normalized records as datasets.
4. Extract risk signals from datasets.
5. Aggregate signals into risk entities and relations.
6. Attach datasets, signals, entities, and notes to cases.
7. Generate evidence packets and notifications.

## Core Principles

- The product is an intelligence collection platform, not a generic content analytics dashboard.
- Every collection task should map to a risk scenario.
- Analysis output must produce actionable signals, entities, relations, cases, or evidence, not only charts.
- The system must preserve source traceability from report output back to raw record reference.
- All collection must stay within lawful, authorized, low-volume, and user-configured boundaries.

## Personas

| Persona | Primary Goal |
| --- | --- |
| Risk operator | Run scheduled collection tasks and review new risk signals. |
| Intelligence analyst | Connect signals, entities, and timelines into cases. |
| Security researcher | Tune signal extractors and identify black-gray behavior patterns. |
| Evidence reviewer | Export evidence packets and verify source traceability. |
| Admin | Configure platforms, auth profiles, rules, notifications, and retention. |

## Risk Scenarios

The platform must support these initial scenario types:

| Scenario | Description |
| --- | --- |
| `lead_diversion` | Detect off-platform diversion, contact points, invite codes, and redirect wording. |
| `gray_recruitment` | Detect recruitment content for black-gray activity, part-time fraud, or account farming. |
| `fraud_promotion` | Detect fraudulent promotion, misleading offers, suspicious service packaging. |
| `seller_risk` | Detect risky sellers, repeated templates, abnormal selling patterns. |
| `product_risk` | Detect risky goods, suspicious prices, disguised products, repeated product listings. |
| `topic_watch` | Track topic-level black-gray activity and coordinated messaging. |

## Platform Scope

Initial platform keys:

- `xhs`
- `dy`
- `ks`
- `wb`
- `zhihu`
- `bili`
- `tieba`
- `xianyu`

Each platform must declare:

- supported entity types
- supported task modes
- platform-specific task fields
- supported signal extractors
- supported analysis capabilities

## Data Objects

## CollectionTask

Required fields:

- `id`
- `task_name`
- `platform`
- `entity_type`
- `task_mode`
- `scenario_type`
- `status`
- `auth_profile_id`
- `task_payload_json`
- `filter_payload_json`
- `runtime_payload_json`
- `storage_profile_json`
- `analysis_profile_json`
- `last_run_at`
- `created_at`
- `updated_at`

Required logic:

- `search` mode requires `keywords`.
- `detail` mode requires `specified_ids`.
- `creator` mode requires `creator_ids`.
- `monitor` mode requires a schedule profile.
- Disabled tasks must not be started by cron jobs.
- A task run must snapshot task configuration before execution.

## TaskRun

Required fields:

- `id`
- `task_id`
- `status`
- `trigger_type`
- `started_at`
- `finished_at`
- `log_path`
- `result_dataset_id`
- `error_message`

Required logic:

- Status must transition through valid states only.
- Failed runs must preserve error message and log reference.
- Successful runs should create or link a result dataset.

## Dataset

Required fields:

- `id`
- `dataset_name`
- `dataset_type`
- `source_platform`
- `source_task_id`
- `source_run_id`
- `scenario_type`
- `record_count`
- `storage_uri`
- `schema_version`
- `snapshot_time`
- `tags`
- `created_at`
- `updated_at`

Required logic:

- Preview must support JSON, JSONL, and CSV.
- Preview must enforce row limits.
- Dataset deletion must not delete original storage unless explicitly requested.
- Dataset records must preserve source platform and source entity reference.

## Signal

Required fields:

- `id`
- `dataset_id`
- `task_run_id`
- `signal_type`
- `signal_source`
- `risk_level`
- `risk_score`
- `summary`
- `payload_json`
- `status`
- `created_at`
- `updated_at`

Required logic:

- Signal extraction must support rule-based extractors.
- Each signal must include enough payload to trace back to a raw or normalized record.
- Signals can be attached to cases.
- Signals can be marked as `new`, `reviewing`, `confirmed`, or `dismissed`.

## RiskEntity

Required fields:

- `id`
- `entity_type`
- `display_name`
- `platform`
- `source_ref`
- `risk_score`
- `status`
- `profile_json`
- `created_at`
- `updated_at`

Required logic:

- Entities can be created from signals.
- Entities can be merged when aliases or repeated identifiers match.
- Entity detail must show related signals, datasets, cases, and relations.

## EntityRelation

Required fields:

- `id`
- `source_entity_id`
- `target_entity_id`
- `relation_type`
- `confidence`
- `evidence_ref_json`
- `created_at`

Required logic:

- Relations must preserve evidence references.
- Relations must support confidence scoring.
- Duplicate relations should be merged or versioned instead of blindly duplicated.

## Case

Required fields:

- `id`
- `case_name`
- `case_type`
- `status`
- `priority`
- `summary`
- `owner`
- `created_at`
- `updated_at`

Required logic:

- Cases can attach datasets, signals, entities, analysis outputs, and evidence packets.
- Cases must support investigation notes.
- Cases must expose a timeline view built from attached objects.

## EvidencePacket

Required fields:

- `id`
- `case_id`
- `packet_name`
- `storage_uri`
- `manifest_json`
- `created_at`
- `updated_at`

Required logic:

- Evidence packets must include a manifest.
- Manifest must list source records, screenshots or raw references when available, generated summaries, and export time.
- Evidence packets must be downloadable.

## Notifications

## NotificationRule

Required fields:

- `id`
- `rule_name`
- `enabled`
- `event_type`
- `risk_level_threshold`
- `scenario_types`
- `platforms`
- `channels`
- `cron_expr`
- `cooldown_minutes`
- `created_at`
- `updated_at`

Required logic:

- Disabled rules must not send notifications.
- `event_type` must support `signal_created`, `case_updated`, `evidence_ready`, and `scheduled_digest`.
- `risk_level_threshold` must filter signal notifications.
- `scenario_types` and `platforms` filters must be optional but respected when configured.
- `cooldown_minutes` must suppress duplicate notifications for the same target.

## Notification Cron Job

The cron job must be implemented concretely. It must not be a placeholder.

Required behavior:

1. Load enabled notification rules.
2. Select rules with `event_type = scheduled_digest`.
3. Evaluate `cron_expr` against current time and last execution time.
4. For due rules, collect new signals, updated cases, and evidence packets since the previous run.
5. Apply platform, scenario, and risk-level filters.
6. Generate a digest payload.
7. Send the digest through configured channels.
8. Persist notification delivery records.
9. Update the rule's last execution timestamp only after delivery attempt is recorded.
10. Record failures without stopping other due rules.

Required delivery record fields:

- `id`
- `rule_id`
- `target_type`
- `target_id`
- `channel`
- `status`
- `payload_json`
- `error_message`
- `created_at`

Supported initial channels:

- `webhook`
- `email`
- `internal_inbox`

## API Requirements

Required route groups:

- `/api/dashboard`
- `/api/tasks`
- `/api/task-runs`
- `/api/datasets`
- `/api/signals`
- `/api/entities`
- `/api/cases`
- `/api/analysis`
- `/api/evidence`
- `/api/notifications`
- `/api/platforms`

Every API group must have:

- request schema
- response schema
- application service
- repository boundary
- tests for success and failure paths

## Frontend Requirements

Required top-level pages:

- Dashboard
- Tasks
- Datasets
- Signals
- Entities
- Cases
- Analysis
- Evidence
- Logs
- Settings

Required frontend behavior:

- The first screen must be an operational dashboard, not a marketing page.
- Navigation must prioritize repeated analyst workflows.
- Tables must support filtering, scanning, and row-level actions.
- Forms must validate required fields before submission.
- Risk levels must be visually distinguishable.
- Case pages must show timeline, attached objects, notes, and evidence actions.

## Production Code Requirements

When implementing this product:

- Do not use placeholders such as `// ... rest of code`, `// logic to be implemented`, `pass` as unfinished business logic, or temporary stubs.
- Do not leave `TODO` comments for required behavior.
- Do not simplify or omit logic branches because code is long.
- If a feature is too large for one change, split it into explicit implementation phases and complete the current phase fully.
- Before final output, verify that every field and branch required by this document is either implemented or explicitly listed as not in scope for the current phase.

## Acceptance Criteria

A feature is complete only when:

1. It has concrete domain models or schemas.
2. It has persistence or a deliberate storage boundary.
3. It has API routes if it is user-facing.
4. It has frontend state if it is part of the UI.
5. It has tests for successful and failed paths.
6. It has no placeholder code.
7. It preserves traceability from output back to source data.
