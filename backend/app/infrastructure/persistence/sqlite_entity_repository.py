from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.entity import EntityRelation, RiskEntity
from ...domain.repositories.entity_repository import EntityRepository


class SQLiteEntityRepository(EntityRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_entities(self) -> list[RiskEntity]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM risk_entities ORDER BY updated_at DESC").fetchall()
        return [self._row_to_entity(row) for row in rows]

    def get_entity(self, entity_id: str) -> RiskEntity | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM risk_entities WHERE id = ?", (entity_id,)).fetchone()
        return self._row_to_entity(row) if row is not None else None

    def save_entity(self, entity: RiskEntity) -> RiskEntity:
        payload = entity.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO risk_entities (
                    id,
                    entity_type,
                    display_name,
                    platform,
                    source_ref,
                    risk_score,
                    status,
                    profile_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    display_name = excluded.display_name,
                    platform = excluded.platform,
                    source_ref = excluded.source_ref,
                    risk_score = excluded.risk_score,
                    status = excluded.status,
                    profile_json = excluded.profile_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["entity_type"],
                    payload["display_name"],
                    payload["platform"],
                    self._dump_json(payload.get("source_ref", {})),
                    payload["risk_score"],
                    payload["status"],
                    self._dump_json(payload.get("profile_json", {})),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return entity

    def delete_entity(self, entity_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM risk_entities WHERE id = ?", (entity_id,))
            connection.commit()
            return cursor.rowcount > 0

    def list_relations(self) -> list[EntityRelation]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM entity_relations ORDER BY updated_at DESC").fetchall()
        return [self._row_to_relation(row) for row in rows]

    def get_relation(self, relation_id: str) -> EntityRelation | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM entity_relations WHERE id = ?", (relation_id,)).fetchone()
        return self._row_to_relation(row) if row is not None else None

    def save_relation(self, relation: EntityRelation) -> EntityRelation:
        payload = relation.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entity_relations (
                    id,
                    source_entity_id,
                    target_entity_id,
                    relation_type,
                    confidence,
                    evidence_ref_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_entity_id = excluded.source_entity_id,
                    target_entity_id = excluded.target_entity_id,
                    relation_type = excluded.relation_type,
                    confidence = excluded.confidence,
                    evidence_ref_json = excluded.evidence_ref_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["source_entity_id"],
                    payload["target_entity_id"],
                    payload["relation_type"],
                    payload["confidence"],
                    self._dump_json(payload.get("evidence_ref_json", {})),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return relation

    def delete_relation(self, relation_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM entity_relations WHERE id = ?", (relation_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_entities (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    source_ref TEXT NOT NULL DEFAULT '{}',
                    risk_score REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON risk_entities (entity_type)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_entities_platform ON risk_entities (platform)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_entities_status ON risk_entities (status)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entity_relations (
                    id TEXT PRIMARY KEY,
                    source_entity_id TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_ref_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON entity_relations (source_entity_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON entity_relations (target_entity_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_type ON entity_relations (relation_type)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_entity(self, row: sqlite3.Row) -> RiskEntity:
        return RiskEntity.model_validate(
            {
                "id": row["id"],
                "entity_type": row["entity_type"],
                "display_name": row["display_name"],
                "platform": row["platform"],
                "source_ref": self._load_json_dict(row["source_ref"]),
                "risk_score": row["risk_score"],
                "status": row["status"],
                "profile_json": self._load_json_dict(row["profile_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _row_to_relation(self, row: sqlite3.Row) -> EntityRelation:
        return EntityRelation.model_validate(
            {
                "id": row["id"],
                "source_entity_id": row["source_entity_id"],
                "target_entity_id": row["target_entity_id"],
                "relation_type": row["relation_type"],
                "confidence": row["confidence"],
                "evidence_ref_json": self._load_json_dict(row["evidence_ref_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _dump_json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
