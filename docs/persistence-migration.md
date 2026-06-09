# Persistence Migration

The platform currently uses JSON files under `backend/storage` as the primary persistence layer. The first migration step is a reversible SQLite staging import that preserves every JSON record exactly before individual repositories are switched to SQL-backed implementations.

## Stage 1: JSON To SQLite Staging

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

The command creates:

- `json_records`: one row per JSON record, keyed by `collection` and `record_id`
- `migration_runs`: audit log for each import

The import is idempotent. Re-running it upserts the same `collection + record_id` rows and records a new migration run.

## Stage 2: Repository Cutover

After staging import is verified, add SQL-backed repositories one aggregate at a time:

1. `datasets` (available behind `MEDIASPIDER_DATASET_REPOSITORY=sqlite`)
2. `collection_tasks` and `task_runs` (available behind `MEDIASPIDER_TASK_REPOSITORY=sqlite`)
3. `signals` (available behind `MEDIASPIDER_SIGNAL_REPOSITORY=sqlite`)
4. `risk_entities` and `entity_relations` (available behind `MEDIASPIDER_ENTITY_REPOSITORY=sqlite`)
5. `cases`, `case_links`, `case_notes` (available behind `MEDIASPIDER_CASE_REPOSITORY=sqlite`)
6. `evidence_packets` (available behind `MEDIASPIDER_EVIDENCE_REPOSITORY=sqlite`)
7. `reports` (available behind `MEDIASPIDER_REPORT_REPOSITORY=sqlite`)
8. `notification_rules`, `notification_deliveries` (available behind `MEDIASPIDER_NOTIFICATION_REPOSITORY=sqlite`)
7. `notification_rules`, `notification_deliveries`

Each cutover should keep the JSON repository tests and add equivalent SQLite repository tests before changing the application container.

To try the SQLite dataset repository locally:

```powershell
$env:MEDIASPIDER_DATASET_REPOSITORY = "sqlite"
$env:MEDIASPIDER_TASK_REPOSITORY = "sqlite"
$env:MEDIASPIDER_SIGNAL_REPOSITORY = "sqlite"
$env:MEDIASPIDER_ENTITY_REPOSITORY = "sqlite"
$env:MEDIASPIDER_CASE_REPOSITORY = "sqlite"
$env:MEDIASPIDER_EVIDENCE_REPOSITORY = "sqlite"
$env:MEDIASPIDER_REPORT_REPOSITORY = "sqlite"
$env:MEDIASPIDER_NOTIFICATION_REPOSITORY = "sqlite"
$env:MEDIASPIDER_SQLITE_PATH = "backend\storage\mediaspider-intel.sqlite3"
.venv\Scripts\python.exe -m backend.app
```

The default remains JSON unless each repository-specific environment variable is set to `sqlite`.

## Stage 3: PostgreSQL

Once SQLite repositories are stable, PostgreSQL support should reuse the same repository contracts. Keep JSON import as a bootstrap and disaster recovery path.
