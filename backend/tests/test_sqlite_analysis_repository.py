from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.domain.models.analysis import AnalysisJob, AnalysisJobStatus, AnalysisOutput, AnalysisScope
from app.infrastructure.persistence.sqlite_analysis_repository import SQLiteAnalysisRepository


def test_sqlite_analysis_repository_persists_jobs_outputs_and_pages(tmp_path):
    repository = SQLiteAnalysisRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = AnalysisJob(
        id="aj_first",
        dataset_id="ds_1",
        analysis_scope=AnalysisScope.COMMON,
        analysis_type="summary",
        status=AnalysisJobStatus.SUCCEEDED,
        parameters_json={"window": "7d"},
        started_at=now.isoformat(),
        finished_at=(now + timedelta(seconds=1)).isoformat(),
        created_at=now,
        updated_at=now,
    )
    second = AnalysisJob(
        id="aj_second",
        dataset_id="ds_1",
        analysis_scope=AnalysisScope.PLATFORM,
        analysis_type="topic_map",
        status=AnalysisJobStatus.RUNNING,
        parameters_json={"platform": "xhs"},
        started_at=(now + timedelta(minutes=1)).isoformat(),
        created_at=now + timedelta(minutes=1),
        updated_at=now + timedelta(minutes=1),
    )
    output = AnalysisOutput(
        id="ao_first",
        analysis_job_id=first.id,
        output_type="summary",
        title="Summary",
        summary="Completed",
        payload_json={"cards": [{"value": 2}]},
        created_at=now,
        updated_at=now,
    )

    repository.save_job(first)
    repository.save_job(second)
    repository.save_output(output)

    assert repository.get_job(first.id) == first
    assert repository.count_jobs() == 2
    assert [item.id for item in repository.list_jobs()] == [second.id, first.id]
    assert [item.id for item in repository.list_jobs(limit=1)] == [second.id]
    assert [item.id for item in repository.list_jobs(offset=1)] == [first.id]
    assert repository.list_outputs(first.id) == [output]
    assert repository.list_outputs(second.id) == []

    updated = first.model_copy(
        update={
            "status": AnalysisJobStatus.FAILED,
            "error_message": "failed",
            "updated_at": now + timedelta(minutes=2),
        }
    )
    repository.save_job(updated)
    assert repository.get_job(first.id) == updated
    assert [item.id for item in repository.list_jobs(limit=1, offset=1)] == [second.id]


def test_app_container_uses_sqlite_analysis_repository_in_global_sqlite_mode(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "platform.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_REPOSITORY_MODE", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    job = container.analysis_service.repository.save_job(
        AnalysisJob(
            dataset_id="ds_1",
            analysis_scope=AnalysisScope.COMMON,
            analysis_type="summary",
        )
    )
    output = container.analysis_service.repository.save_output(
        AnalysisOutput(
            analysis_job_id=job.id,
            output_type="summary",
            title="Container output",
        )
    )

    assert sqlite_path.exists()
    assert container.analysis_service.get_job(job.id) == job
    assert container.analysis_service.get_outputs(job.id) == [output]
