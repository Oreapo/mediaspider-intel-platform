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


def test_sqlite_entity_repository_filters_counts_and_paginates(tmp_path):
    repository = SQLiteEntityRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    entities = [
        _entity("ent_account", now).model_copy(
            update={
                "entity_type": RiskEntityType.ACCOUNT,
                "display_name": "risk_account 100%",
                "source_ref": {"source_entity_id": "account_001"},
                "risk_score": 72,
                "profile_json": {"aliases": ["risk_account", "ra001"], "linked_signal_ids": ["sig_account"]},
            }
        ),
        _entity("ent_contact", now + timedelta(minutes=1)).model_copy(
            update={
                "display_name": "abc12345",
                "source_ref": {"contact_point": "abc12345"},
                "risk_score": 88,
                "profile_json": {"aliases": ["abc12345"], "linked_signal_ids": ["sig_contact"]},
            }
        ),
        _entity("ent_seller", now + timedelta(minutes=2)).model_copy(
            update={
                "entity_type": RiskEntityType.SELLER,
                "display_name": "seller_1",
                "platform": PlatformKey.XIANYU,
                "source_ref": {"seller_id": "seller_1"},
                "risk_score": 45,
                "status": RiskEntityStatus.DISMISSED,
                "profile_json": {"aliases": ["seller_1"]},
            }
        ),
    ]
    for entity in entities:
        repository.save_entity(entity)

    assert [item.id for item in repository.list_entities(platform=PlatformKey.XIANYU)] == ["ent_seller"]
    assert [item.id for item in repository.list_entities(status=RiskEntityStatus.DISMISSED)] == ["ent_seller"]
    assert [item.id for item in repository.list_entities(query="ra001")] == ["ent_account"]
    assert [item.id for item in repository.list_entities(query="sig_contact")] == ["ent_contact"]
    assert [item.id for item in repository.list_entities(query="100%")] == ["ent_account"]
    assert repository.count_entities(min_risk_score=80) == 1
    assert [item.id for item in repository.list_entities(limit=1, offset=1)] == ["ent_contact"]
    assert repository.count_entities() == 3
