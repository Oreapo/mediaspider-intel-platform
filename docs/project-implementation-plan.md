# Project Implementation Plan

## Current Baseline

The repository currently contains two product lines:

- Existing `MediaSpider` crawler code under the repository root.
- Next-generation anti-black-gray intelligence platform under `products/mediaspider-intel-platform`.

The new platform already has:

- FastAPI backend scaffold.
- Vue + Vite frontend scaffold.
- Working `tasks`, `datasets`, `analysis`, and `platforms` API groups.
- JSON persistence repositories for task, dataset, and analysis objects.
- Requirements and design documents for anti-black-gray intelligence workflows.

The new platform does not yet have:

- Real crawler execution integration.
- Risk signal extraction implementation.
- Risk entity and relation implementation.
- Case management implementation.
- Evidence packet implementation.
- Notification rules and cron delivery implementation.

## Target Product Shape

The platform should evolve into an anti-black-gray intelligence workbench with this core flow:

1. Create scenario-driven collection tasks.
2. Run controlled platform collection.
3. Materialize collection output into datasets.
4. Extract risk signals from datasets.
5. Aggregate signals into risk entities and relations.
6. Attach datasets, signals, entities, notes, and analysis outputs to cases.
7. Export evidence packets and send notifications.

## Implementation Phases

## Phase 1: Align Existing Skeleton With Requirements

Goal:

Make the existing `tasks` and `datasets` skeleton match the requirements before adding new modules.

Required work:

- Add `scenario_type` to task models, schemas, frontend forms, and dataset records.
- Preserve task snapshots in task runs.
- Expose platform signal extractors and analysis capability declarations.
- Keep backend tests passing.
- Keep frontend production build passing.

Completion criteria:

- `CollectionTask` includes `scenario_type`.
- `Dataset` includes `scenario_type`.
- `TaskRun` includes `task_snapshot_json`.
- `/api/platforms` returns `supported_signal_extractors` and `supported_analysis_types`.
- The task form and dataset form both collect risk scenario.

## Phase 2: Risk Signals

Goal:

Add the first anti-black-gray-specific object layer.

Required backend modules:

- `domain/models/signal.py`
- `domain/repositories/signal_repository.py`
- `infrastructure/persistence/json_signal_repository.py`
- `application/signal_service.py`
- `api/schemas/signal.py`
- `api/routes/signals.py`

Required frontend modules:

- `src/api/signals.ts`
- `src/composables/useSignals.ts`
- `src/views/SignalsView.vue`
- router and sidebar entries

Required logic:

- Create signals manually for investigation workflow.
- Extract signals from dataset preview rows using rule-based extractors.
- Support signal statuses: `new`, `reviewing`, `confirmed`, `dismissed`.
- Preserve source traceability to dataset, row, and raw reference where available.

Completion criteria:

- Signals can be listed, read, extracted, and status-updated.
- Signal tests cover successful extraction, missing dataset, invalid status, and source traceability.

## Phase 3: Risk Entities And Relations

Goal:

Represent accounts, sellers, products, contact points, and their relationships.

Required backend modules:

- `domain/models/entity.py`
- `domain/repositories/entity_repository.py`
- `infrastructure/persistence/json_entity_repository.py`
- `application/entity_service.py`
- `api/schemas/entity.py`
- `api/routes/entities.py`

Required logic:

- Create entities from signals.
- Merge entities by aliases or repeated identifiers.
- Create relation edges with confidence and evidence references.
- Query entity details with related signals, relations, and cases.

Completion criteria:

- Entities can be created from confirmed signals.
- Relations preserve evidence references.
- Duplicate relation handling is deterministic.

## Phase 4: Cases

Goal:

Introduce the investigation container for analysts.

Required backend modules:

- `domain/models/case.py`
- `domain/repositories/case_repository.py`
- `infrastructure/persistence/json_case_repository.py`
- `application/case_service.py`
- `api/schemas/case.py`
- `api/routes/cases.py`

Required frontend modules:

- `src/api/cases.ts`
- `src/composables/useCases.ts`
- `src/views/CasesView.vue`

Required logic:

- Create and update cases.
- Attach datasets, signals, entities, and analysis outputs.
- Add investigation notes.
- Build case timeline from linked objects.

Completion criteria:

- A case can contain multiple linked object types.
- Timeline output is deterministic and source-referenced.

## Phase 5: Evidence Packets

Goal:

Make investigation output exportable and traceable.

Required backend modules:

- `domain/models/evidence.py`
- `domain/repositories/evidence_repository.py`
- `infrastructure/persistence/json_evidence_repository.py`
- `application/evidence_service.py`
- `api/schemas/evidence.py`
- `api/routes/evidence.py`

Required logic:

- Generate evidence packet manifests from cases.
- Include source records, signal summaries, entity references, and export timestamps.
- Persist packet metadata.
- Provide download endpoint for generated files.

Completion criteria:

- Evidence packet generation produces a manifest.
- Download endpoint returns a concrete artifact.
- Packet records link back to cases.

## Phase 6: Notifications

Goal:

Add operational notification rules and scheduled digests.

Required backend modules:

- `domain/models/notification.py`
- `domain/repositories/notification_repository.py`
- `infrastructure/persistence/json_notification_repository.py`
- `application/notification_service.py`
- `application/notification_scheduler.py`
- `api/schemas/notification.py`
- `api/routes/notifications.py`

Required cron behavior:

- Load enabled rules.
- Evaluate `cron_expr`.
- Collect due events since last execution.
- Apply platform, scenario, risk-level, and cooldown filters.
- Deliver through `webhook`, `email`, and `internal_inbox`.
- Persist delivery records.
- Isolate failures per rule.

Completion criteria:

- Scheduled digest rules are executable by application service.
- Delivery records are persisted for success and failure.
- Tests cover disabled rules, filtering, cooldown, delivery failure, and last-run update.

## Phase 7: Real Crawler Integration

Goal:

Connect new task runs to existing `MediaSpider` platform crawlers.

Required work:

- Build a task-to-config adapter.
- Execute existing crawler entrypoints in a controlled process boundary.
- Capture logs and exit status.
- Materialize output files into datasets.
- Preserve rate limits and safe collection controls.

Initial platform order:

1. `xhs`
2. `dy`
3. `wb`
4. `xianyu`

Reasoning:

- `xhs`, `dy`, and `wb` already exist in the current crawler code.
- `xianyu` is required by the product plan but does not yet exist in the current crawler factory.

## Phase 8: Platform-Specific Extractors

Goal:

Turn generic signal extraction into useful platform intelligence.

Initial extractors:

- `xhs`: contact points, lead-diversion terms, template similarity.
- `dy`: synchronized posting patterns, diversion wording, repeated script phrases.
- `wb`: coordinated propagation, repeated wording, abnormal topic activity.
- `xianyu`: risky product wording, abnormal price bands, seller template reuse.

Completion criteria:

- Each extractor emits `Signal` records with source traceability.
- Extractors are declared in platform capability models.
- Extractor tests use fixed local sample data.

## Engineering Rules

- Implement one phase at a time.
- Do not create UI pages without backed API behavior unless the page is explicitly marked as outside the current implementation phase in documentation.
- Do not leave placeholder business logic.
- Every user-facing route group must include schema, service, repository boundary, and tests.
- Every frontend page must have real API state, loading state, error state, and empty state.
