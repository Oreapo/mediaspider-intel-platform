# Code Gap Analysis

## Scope

This analysis compares the current repository implementation with `docs/requirements.md`.

It covers:

- Existing root `MediaSpider` crawler code.
- New platform backend under `products/mediaspider-intel-platform/backend`.
- New platform frontend under `products/mediaspider-intel-platform/frontend`.

## Summary

The current codebase has a usable crawler foundation and a runnable next-generation platform skeleton.  
The gap is not basic project setup. The gap is product-specific anti-black-gray workflow implementation.

## Existing Root Crawler

## Implemented

- Platform factory exists in `main.py`.
- Implemented crawler directories:
  - `xhs`
  - `douyin`
  - `kuaishou`
  - `bilibili`
  - `weibo`
  - `tieba`
  - `zhihu`
- Existing crawler execution supports search, detail, and creator flows according to platform implementation.
- Existing collection has rate-limit and count-related configuration controls.

## Gaps

- `xianyu` is required by the product plan but is not implemented in `media_platform` or `CrawlerFactory`.
- Existing crawler output is file/store oriented, not dataset/materialization oriented for the new platform.
- Existing crawler execution is not yet connected to new `TaskRun` records.
- Existing code does not emit `Signal`, `RiskEntity`, `Case`, or `EvidencePacket` objects.

## Required Modifications

- Add `media_platform/xianyu` only after a scoped MVP design is approved.
- Add a task execution adapter that maps new `CollectionTask` into existing crawler configuration.
- Add output materialization that turns crawler result files into `Dataset` records.
- Preserve current crawler safety controls when called from the new platform.

## New Backend

## Implemented

- `tasks` route group.
- `datasets` route group.
- `analysis` route group.
- `platforms` route group.
- JSON repositories for tasks, datasets, and analysis jobs.
- `xianyu` appears in platform capability declarations.
- CORS configured for local frontend development.

## Recently Aligned

- `CollectionTask` now carries `scenario_type`.
- `Dataset` now carries `scenario_type`.
- `TaskRun` now carries `task_snapshot_json`.
- Platform models now declare `supported_signal_extractors` and `supported_analysis_types`.

## Gaps

- No `/api/signals` implementation.
- No `/api/entities` implementation.
- No `/api/cases` implementation.
- No `/api/evidence` implementation.
- No `/api/notifications` implementation.
- No `/api/dashboard` implementation.
- No `/api/task-runs` standalone route group.
- `analysis` currently produces summary output only; it does not yet create signals, entities, relations, or cases.
- No notification cron implementation.
- No persistent database migrations. SQLAlchemy models are draft tables, while runtime uses JSON repositories.

## Required Modifications

Priority order:

1. Add `signals`.
2. Add `entities`.
3. Add `cases`.
4. Add `evidence`.
5. Add `notifications`.
6. Add crawler execution adapter.
7. Add real dashboard aggregation.

## New Frontend

## Implemented

- Vue + Vite project.
- Route shell with sidebar and header.
- Existing pages:
  - Dashboard
  - Tasks
  - Datasets
  - Analysis
  - Reports
  - Logs
  - Settings
- API clients for tasks, datasets, analysis, and platforms.
- Build passes with current frontend code.

## Recently Aligned

- Task form now collects risk scenario.
- Dataset form now collects risk scenario.
- Types include `scenario_type`.

## Gaps

- Required pages missing:
  - Signals
  - Entities
  - Cases
  - Evidence
- Current Reports page is not aligned with the evidence-packet requirement.
- Current Logs page is not connected to task-run logs.
- Current Settings page is not connected to platform profiles, notification rules, or retention settings.
- Dashboard does not yet consume real risk summary APIs.

## Required Modifications

- Add frontend pages only when corresponding API groups exist.
- Replace Reports with Evidence-first workflow after `evidence` API is implemented.
- Add row-level actions for signal review, entity merge, case attach, and evidence export.
- Use risk levels consistently in table and detail states.

## Documentation

## Implemented

- Product vision.
- Architecture.
- Requirements.
- Backend API design.
- Database model.
- Frontend IA.
- Page contracts.
- Anti-black-gray design.
- Project implementation plan.

## Gaps

- Need a migration plan from root crawler output to new dataset model.
- Need platform-specific signal extractor specifications.
- Need notification delivery channel specifications.

## Recommended Next Code Step

Implement `signals` as the next complete slice.

Reasoning:

- It is the first missing object after datasets.
- It unlocks Entities and Cases.
- It can be implemented without real crawler integration by using existing dataset preview input.
- It provides immediate product value for anti-black-gray workflows.

Minimum complete `signals` slice:

- `Signal` domain model.
- JSON signal repository.
- Signal application service.
- Signal schemas.
- Signal routes.
- Rule-based extraction from dataset rows.
- Frontend Signals page.
- Backend API tests.
- Frontend build verification.
