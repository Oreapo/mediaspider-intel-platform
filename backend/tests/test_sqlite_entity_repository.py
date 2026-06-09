from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies.container import AppContainer
from app.api.schemas.entity import RiskEntityCreateRequest
from app.domain.models.entity import (
    EntityRelation,
    RiskEntity,
    RiskEntityStatus,
    RiskEntityType,
)
from app.domain.models.platform import PlatformKey
from app.infrastructure.persistence.sqlite_entity_repository import SQLiteEntityRepository


def _entity(entity_id: str, updated_at: datetime) -> RiskEntity:
    return RiskEntity(
        id=entity_id,
        entity_type=RiskEntityType.CONTACT_POINT,
        display_name=f"contact-{entity_id}",
        platform=PlatformKey.XHS,
        source_ref={"contact_point": f"contact-{entity_id}"},
        risk_score=86.5,
        status=RiskEntityStatus.ACTIVE,
        profile_json={"aliases": [f"contact-{entity_id}"]},
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_sqlite_entity_repository_crud_and_relations(tmp_path):
    repository = SQLiteEntityRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = _entity("ent_first", now)
    second = _entity("ent_second", now + timedelta(minutes=1))

    repository.save_entity(first)
    repository.save_entity(second)

    assert repository.get_entity("ent_first") == first
    assert [item.id for item in repository.list_entities()] == ["ent_second", "ent_first"]

    updated = first.model_copy(
        update={
            "status": RiskEntityStatus.DISMISSED,
            "profile_json": {"aliases": ["updated"]},
            "updated_at": now + timedelta(minutes=2),
        }
    )
    repository.save_entity(updated)
    assert repository.get_entity("ent_first").status == RiskEntityStatus.DISMISSED
    assert repository.get_entity("ent_first").profile_json["aliases"] == ["updated"]

    relation = EntityRelation(
        id="rel_1",
        source_entity_id="ent_first",
        target_entity_id="ent_second",
        relation_type="uses_contact_point",
        confidence=0.91,
        evidence_ref_json={"signal_id": "sig_1"},
        created_at=now,
        updated_at=now,
    )
    repository.save_relation(relation)
    assert repository.get_relation("rel_1") == relation
    assert [item.id for item in repository.list_relations()] == ["rel_1"]

    assert repository.delete_relation("rel_1") is True
    assert repository.delete_relation("missing") is False
    assert repository.delete_entity("ent_second") is True
    assert repository.delete_entity("missing") is False
    assert [item.id for item in repository.list_entities()] == ["ent_first"]


def test_app_container_can_switch_entity_repository_to_sqlite(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "storage" / "entities.sqlite3"
    monkeypatch.setenv("MEDIASPIDER_ENTITY_REPOSITORY", "sqlite")
    monkeypatch.setenv("MEDIASPIDER_SQLITE_PATH", str(sqlite_path))

    container = AppContainer(tmp_path)
    entity = container.entity_service.create_entity(
        RiskEntityCreateRequest(
            entity_type=RiskEntityType.CONTACT_POINT,
            display_name="abc12345",
            platform=PlatformKey.XHS,
            source_ref={"contact_point": "abc12345"},
            risk_score=90,
            profile_json={"aliases": ["abc12345"]},
        )
    )

    assert sqlite_path.exists()
    assert container.entity_service.get_entity(entity.id).display_name == "abc12345"
