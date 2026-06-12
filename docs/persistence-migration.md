# Persistence Migration

The platform currently uses JSON files under `backend/storage` as the primary persistence layer. The first migration step is a reversible SQLite staging import that preserves every JSON record exactly before individual repositories are switched to SQL-backed implementations.

## JSON To SQLite Migration

Run:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\migrate_json_to_sqlite.py
```

Optional paths:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\migrate_json_to_sqlite.py `
  --storage-dir backend\storage `
  --sqlite-path backend\storage\mediaspider-intel.sqlite3
```

By default the command performs both:

- staging: preserves every source record in `json_records`
- activation: validates known domain models and upserts them into native SQLite repository tables
- audit: records staging and native import counts in `migration_runs`

Records without a stable `id`, or records that fail the current domain validation, remain in
`json_records` but are skipped during native activation. The command reports both counts.

For a staging-only backup:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\migrate_json_to_sqlite.py --staging-only
```

The import is idempotent. Re-running it upserts the same source and native records and records
a new migration run.

The Docker Compose backend enables `MEDIASPIDER_AUTO_MIGRATE_JSON=true`. Its startup command
runs this migration only when SQLite mode is selected and the configured SQLite file does not
exist. It migrates into a temporary database and only replaces the configured target after the
full migration succeeds. Once the database exists, startup skips migration so stale JSON cannot
overwrite newer SQLite records.

## Repository Cutover

After staging import is verified, add SQL-backed repositories one aggregate at a time:

1. `datasets` (available behind `MEDIASPIDER_DATASET_REPOSITORY=sqlite`)
2. `collection_tasks` and `task_runs` (available behind `MEDIASPIDER_TASK_REPOSITORY=sqlite`)
3. `analysis_jobs` and `analysis_outputs` (available behind `MEDIASPIDER_ANALYSIS_REPOSITORY=sqlite`)
4. `signals` (available behind `MEDIASPIDER_SIGNAL_REPOSITORY=sqlite`)
5. `risk_entities` and `entity_relations` (available behind `MEDIASPIDER_ENTITY_REPOSITORY=sqlite`)
6. `cases`, `case_links`, `case_notes` (available behind `MEDIASPIDER_CASE_REPOSITORY=sqlite`)
7. `evidence_packets` (available behind `MEDIASPIDER_EVIDENCE_REPOSITORY=sqlite`)
8. `reports` (available behind `MEDIASPIDER_REPORT_REPOSITORY=sqlite`)
9. `notification_rules`, `notification_deliveries` (available behind `MEDIASPIDER_NOTIFICATION_REPOSITORY=sqlite`)
10. `platform_profiles` (available behind `MEDIASPIDER_PLATFORM_PROFILE_REPOSITORY=sqlite`)
11. `audit_events` (available behind `MEDIASPIDER_AUDIT_REPOSITORY=sqlite`)

Each cutover should keep the JSON repository tests and add equivalent SQLite repository tests before changing the application container.

To try the SQLite dataset repository locally:

```powershell
$env:MEDIASPIDER_DATASET_REPOSITORY = "sqlite"
$env:MEDIASPIDER_TASK_REPOSITORY = "sqlite"
$env:MEDIASPIDER_ANALYSIS_REPOSITORY = "sqlite"
$env:MEDIASPIDER_SIGNAL_REPOSITORY = "sqlite"
$env:MEDIASPIDER_ENTITY_REPOSITORY = "sqlite"
$env:MEDIASPIDER_CASE_REPOSITORY = "sqlite"
$env:MEDIASPIDER_EVIDENCE_REPOSITORY = "sqlite"
$env:MEDIASPIDER_REPORT_REPOSITORY = "sqlite"
$env:MEDIASPIDER_NOTIFICATION_REPOSITORY = "sqlite"
$env:MEDIASPIDER_PLATFORM_PROFILE_REPOSITORY = "sqlite"
$env:MEDIASPIDER_AUDIT_REPOSITORY = "sqlite"
$env:MEDIASPIDER_SQLITE_PATH = "backend\storage\mediaspider-intel.sqlite3"
.venv\Scripts\python.exe -m backend.app
```

The default remains JSON unless a repository-specific environment variable or
`MEDIASPIDER_REPOSITORY_MODE=sqlite` selects SQLite.

## PostgreSQL

Once SQLite repositories are stable, PostgreSQL support should reuse the same repository contracts. Keep JSON import as a bootstrap and disaster recovery path.
