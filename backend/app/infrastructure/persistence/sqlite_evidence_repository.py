from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.evidence import EvidencePacket
from ...domain.repositories.evidence_repository import EvidenceRepository


class SQLiteEvidenceRepository(EvidenceRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_packets(self) -> list[EvidencePacket]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM evidence_packets ORDER BY updated_at DESC").fetchall()
        return [self._row_to_packet(row) for row in rows]

    def get_packet(self, packet_id: str) -> EvidencePacket | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM evidence_packets WHERE id = ?", (packet_id,)).fetchone()
        return self._row_to_packet(row) if row is not None else None

    def save_packet(self, packet: EvidencePacket) -> EvidencePacket:
        payload = packet.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO evidence_packets (
                    id,
                    case_id,
                    packet_name,
                    storage_uri,
                    manifest_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    case_id = excluded.case_id,
                    packet_name = excluded.packet_name,
                    storage_uri = excluded.storage_uri,
                    manifest_json = excluded.manifest_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["case_id"],
                    payload["packet_name"],
                    payload["storage_uri"],
                    json.dumps(payload.get("manifest_json", {}), ensure_ascii=False, sort_keys=True),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return packet

    def delete_packet(self, packet_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM evidence_packets WHERE id = ?", (packet_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_packets (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    packet_name TEXT NOT NULL,
                    storage_uri TEXT NOT NULL,
                    manifest_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_evidence_packets_case_id ON evidence_packets (case_id)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_packet(self, row: sqlite3.Row) -> EvidencePacket:
        return EvidencePacket.model_validate(
            {
                "id": row["id"],
                "case_id": row["case_id"],
                "packet_name": row["packet_name"],
                "storage_uri": row["storage_uri"],
                "manifest_json": self._load_json_dict(row["manifest_json"]),
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
