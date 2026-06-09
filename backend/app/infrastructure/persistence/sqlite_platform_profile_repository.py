from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.platform import AuthType, PlatformKey, PlatformProfile
from ...domain.repositories.platform_profile_repository import PlatformProfileRepository


class SQLitePlatformProfileRepository(PlatformProfileRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_profiles(self, platform: PlatformKey | None = None) -> list[PlatformProfile]:
        with self._connect() as connection:
            if platform is None:
                rows = connection.execute("SELECT * FROM platform_profiles ORDER BY updated_at DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM platform_profiles WHERE platform = ? ORDER BY updated_at DESC",
                    (platform.value,),
                ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile(self, profile_id: str) -> PlatformProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM platform_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        return self._row_to_profile(row) if row is not None else None

    def save_profile(self, profile: PlatformProfile) -> PlatformProfile:
        payload = profile.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO platform_profiles (
                    id,
                    platform,
                    profile_name,
                    auth_type,
                    credentials_ref,
                    settings_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    platform = excluded.platform,
                    profile_name = excluded.profile_name,
                    auth_type = excluded.auth_type,
                    credentials_ref = excluded.credentials_ref,
                    settings_json = excluded.settings_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["platform"],
                    payload["profile_name"],
                    payload["auth_type"],
                    payload.get("credentials_ref", ""),
                    self._dump_json(payload.get("settings_json", {})),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM platform_profiles WHERE id = ?", (profile_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_profiles (
                    id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    auth_type TEXT NOT NULL,
                    credentials_ref TEXT NOT NULL DEFAULT '',
                    settings_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_platform_profiles_platform ON platform_profiles (platform)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_profile(self, row: sqlite3.Row) -> PlatformProfile:
        return PlatformProfile(
            id=row["id"],
            platform=PlatformKey(row["platform"]),
            profile_name=row["profile_name"],
            auth_type=AuthType(row["auth_type"]),
            credentials_ref=row["credentials_ref"],
            settings_json=self._load_json_dict(row["settings_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _dump_json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
