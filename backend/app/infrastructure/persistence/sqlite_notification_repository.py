from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationRule,
)
from ...domain.repositories.notification_repository import NotificationRepository


class SQLiteNotificationRepository(NotificationRepository):
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def list_rules(self) -> list[NotificationRule]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM notification_rules ORDER BY updated_at DESC").fetchall()
        return [self._row_to_rule(row) for row in rows]

    def get_rule(self, rule_id: str) -> NotificationRule | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM notification_rules WHERE id = ?", (rule_id,)).fetchone()
        return self._row_to_rule(row) if row is not None else None

    def save_rule(self, rule: NotificationRule) -> NotificationRule:
        payload = rule.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notification_rules (
                    id,
                    rule_name,
                    enabled,
                    event_type,
                    risk_level_threshold,
                    scenario_types,
                    platforms,
                    channels,
                    cron_expr,
                    cooldown_minutes,
                    channel_config_json,
                    last_executed_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    rule_name = excluded.rule_name,
                    enabled = excluded.enabled,
                    event_type = excluded.event_type,
                    risk_level_threshold = excluded.risk_level_threshold,
                    scenario_types = excluded.scenario_types,
                    platforms = excluded.platforms,
                    channels = excluded.channels,
                    cron_expr = excluded.cron_expr,
                    cooldown_minutes = excluded.cooldown_minutes,
                    channel_config_json = excluded.channel_config_json,
                    last_executed_at = excluded.last_executed_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["rule_name"],
                    1 if payload["enabled"] else 0,
                    payload["event_type"],
                    payload["risk_level_threshold"],
                    self._dump_json(payload.get("scenario_types", [])),
                    self._dump_json(payload.get("platforms", [])),
                    self._dump_json(payload.get("channels", [])),
                    payload["cron_expr"],
                    payload["cooldown_minutes"],
                    self._dump_json(payload.get("channel_config_json", {})),
                    payload.get("last_executed_at"),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM notification_rules WHERE id = ?", (rule_id,))
            connection.commit()
            return cursor.rowcount > 0

    def list_deliveries(
        self,
        *,
        rule_id: str | None = None,
        status: NotificationDeliveryStatus | None = None,
        channel: NotificationChannel | None = None,
        target_type: str = "",
        target_id: str = "",
        is_read: bool | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NotificationDelivery]:
        where_clause, parameters = self._delivery_filter_query(
            rule_id=rule_id,
            status=status,
            channel=channel,
            target_type=target_type,
            target_id=target_id,
            is_read=is_read,
            query=query,
        )
        statement = f"SELECT * FROM notification_deliveries{where_clause} ORDER BY created_at DESC"
        if limit is not None:
            statement += " LIMIT ?"
            parameters.append(limit)
        elif offset > 0:
            statement += " LIMIT -1"
        if offset > 0:
            statement += " OFFSET ?"
            parameters.append(offset)
        with self._connect() as connection:
            rows = connection.execute(statement, tuple(parameters)).fetchall()
        return [self._row_to_delivery(row) for row in rows]

    def count_deliveries(
        self,
        *,
        rule_id: str | None = None,
        status: NotificationDeliveryStatus | None = None,
        channel: NotificationChannel | None = None,
        target_type: str = "",
        target_id: str = "",
        is_read: bool | None = None,
        query: str = "",
    ) -> int:
        where_clause, parameters = self._delivery_filter_query(
            rule_id=rule_id,
            status=status,
            channel=channel,
            target_type=target_type,
            target_id=target_id,
            is_read=is_read,
            query=query,
        )
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM notification_deliveries{where_clause}",
                tuple(parameters),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def get_delivery(self, delivery_id: str) -> NotificationDelivery | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM notification_deliveries WHERE id = ?",
                (delivery_id,),
            ).fetchone()
        return self._row_to_delivery(row) if row is not None else None

    def save_delivery(self, delivery: NotificationDelivery) -> NotificationDelivery:
        payload = delivery.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notification_deliveries (
                    id,
                    rule_id,
                    target_type,
                    target_id,
                    channel,
                    status,
                    payload_json,
                    error_message,
                    retry_count,
                    last_attempt_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    rule_id = excluded.rule_id,
                    target_type = excluded.target_type,
                    target_id = excluded.target_id,
                    channel = excluded.channel,
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    error_message = excluded.error_message,
                    retry_count = excluded.retry_count,
                    last_attempt_at = excluded.last_attempt_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["rule_id"],
                    payload["target_type"],
                    payload["target_id"],
                    payload["channel"],
                    payload["status"],
                    self._dump_json(payload.get("payload_json", {})),
                    payload.get("error_message", ""),
                    payload.get("retry_count", 0),
                    payload.get("last_attempt_at"),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        return delivery

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_rules (
                    id TEXT PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    event_type TEXT NOT NULL,
                    risk_level_threshold TEXT NOT NULL,
                    scenario_types TEXT NOT NULL DEFAULT '[]',
                    platforms TEXT NOT NULL DEFAULT '[]',
                    channels TEXT NOT NULL DEFAULT '[]',
                    cron_expr TEXT NOT NULL DEFAULT '*/30 * * * *',
                    cooldown_minutes INTEGER NOT NULL DEFAULT 60,
                    channel_config_json TEXT NOT NULL DEFAULT '{}',
                    last_executed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_rules_enabled ON notification_rules (enabled)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_rules_event_type ON notification_rules (event_type)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._add_column_if_missing(connection, "notification_deliveries", "retry_count", "INTEGER NOT NULL DEFAULT 0")
            self._add_column_if_missing(connection, "notification_deliveries", "last_attempt_at", "TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_deliveries_rule ON notification_deliveries (rule_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_deliveries_target ON notification_deliveries (target_type, target_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_deliveries_status ON notification_deliveries (status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_deliveries_channel ON notification_deliveries (channel)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_notification_deliveries_created_at ON notification_deliveries (created_at DESC)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_rule(self, row: sqlite3.Row) -> NotificationRule:
        return NotificationRule.model_validate(
            {
                "id": row["id"],
                "rule_name": row["rule_name"],
                "enabled": bool(row["enabled"]),
                "event_type": row["event_type"],
                "risk_level_threshold": row["risk_level_threshold"],
                "scenario_types": self._load_json_list(row["scenario_types"]),
                "platforms": self._load_json_list(row["platforms"]),
                "channels": self._load_json_list(row["channels"]),
                "cron_expr": row["cron_expr"],
                "cooldown_minutes": row["cooldown_minutes"],
                "channel_config_json": self._load_json_dict(row["channel_config_json"]),
                "last_executed_at": row["last_executed_at"],
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _row_to_delivery(self, row: sqlite3.Row) -> NotificationDelivery:
        return NotificationDelivery.model_validate(
            {
                "id": row["id"],
                "rule_id": row["rule_id"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "channel": row["channel"],
                "status": row["status"],
                "payload_json": self._load_json_dict(row["payload_json"]),
                "error_message": row["error_message"],
                "retry_count": row["retry_count"] if "retry_count" in row.keys() else 0,
                "last_attempt_at": row["last_attempt_at"] if "last_attempt_at" in row.keys() else None,
                "created_at": self._parse_datetime(row["created_at"]),
                "updated_at": self._parse_datetime(row["updated_at"]),
            }
        )

    def _add_column_if_missing(self, connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if column not in {row["name"] for row in rows}:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _delivery_filter_query(
        self,
        *,
        rule_id: str | None,
        status: NotificationDeliveryStatus | None,
        channel: NotificationChannel | None,
        target_type: str,
        target_id: str,
        is_read: bool | None,
        query: str,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if rule_id:
            clauses.append("rule_id = ?")
            parameters.append(rule_id)
        if status:
            clauses.append("status = ?")
            parameters.append(status.value)
        if channel:
            clauses.append("channel = ?")
            parameters.append(channel.value)
        normalized_target_type = target_type.strip().lower()
        if normalized_target_type:
            clauses.append("lower(target_type) = ?")
            parameters.append(normalized_target_type)
        normalized_target_id = target_id.strip()
        if normalized_target_id:
            clauses.append("target_id = ?")
            parameters.append(normalized_target_id)
        if is_read is not None:
            read_expression = (
                "coalesce(CAST(json_extract(payload_json, '$._inbox.read_at') AS TEXT), '') "
                "NOT IN ('', '0', 'false')"
            )
            clauses.append(read_expression if is_read else f"NOT ({read_expression})")
        needle = query.strip().lower()
        if needle:
            search_columns = (
                "id",
                "rule_id",
                "target_type",
                "target_id",
                "channel",
                "status",
                "error_message",
                "payload_json",
            )
            query_clauses = [
                f"lower(coalesce({column}, '')) LIKE ? ESCAPE '\\'" for column in search_columns
            ]
            clauses.append(f"({' OR '.join(query_clauses)})")
            parameters.extend([self._like_value(needle)] * len(query_clauses))
        return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), parameters

    def _like_value(self, value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def _dump_json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _load_json_dict(self, value: str) -> dict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _load_json_list(self, value: str) -> list[Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value)
