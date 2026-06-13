from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationRule,
)
from ...domain.repositories.notification_repository import NotificationRepository


class JsonNotificationRepository(NotificationRepository):
    def __init__(self, rules_file: Path, deliveries_file: Path):
        self.rules_file = rules_file
        self.deliveries_file = deliveries_file

    def list_rules(self) -> list[NotificationRule]:
        return sorted(self._load_rules(), key=lambda rule: rule.updated_at, reverse=True)

    def get_rule(self, rule_id: str) -> NotificationRule | None:
        for rule in self._load_rules():
            if rule.id == rule_id:
                return rule
        return None

    def save_rule(self, rule: NotificationRule) -> NotificationRule:
        rules = self._load_rules()
        replaced = False
        for index, existing in enumerate(rules):
            if existing.id == rule.id:
                rules[index] = rule
                replaced = True
                break
        if not replaced:
            rules.append(rule)
        self._save_rules(rules)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        rules = self._load_rules()
        filtered = [rule for rule in rules if rule.id != rule_id]
        if len(filtered) == len(rules):
            return False
        self._save_rules(filtered)
        return True

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
        deliveries = self._filtered_deliveries(
            rule_id=rule_id,
            status=status,
            channel=channel,
            target_type=target_type,
            target_id=target_id,
            is_read=is_read,
            query=query,
        )
        if offset > 0:
            deliveries = deliveries[offset:]
        if limit is not None:
            deliveries = deliveries[:limit]
        return deliveries

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
        return len(
            self._filtered_deliveries(
                rule_id=rule_id,
                status=status,
                channel=channel,
                target_type=target_type,
                target_id=target_id,
                is_read=is_read,
                query=query,
            )
        )

    def get_delivery(self, delivery_id: str) -> NotificationDelivery | None:
        for delivery in self._load_deliveries():
            if delivery.id == delivery_id:
                return delivery
        return None

    def save_delivery(self, delivery: NotificationDelivery) -> NotificationDelivery:
        deliveries = self._load_deliveries()
        replaced = False
        for index, existing in enumerate(deliveries):
            if existing.id == delivery.id:
                deliveries[index] = delivery
                replaced = True
                break
        if not replaced:
            deliveries.append(delivery)
        self._save_deliveries(deliveries)
        return delivery

    def _load_rules(self) -> list[NotificationRule]:
        return self._load_model_list(self.rules_file, NotificationRule)

    def _load_deliveries(self) -> list[NotificationDelivery]:
        return self._load_model_list(self.deliveries_file, NotificationDelivery)

    def _filtered_deliveries(
        self,
        *,
        rule_id: str | None,
        status: NotificationDeliveryStatus | None,
        channel: NotificationChannel | None,
        target_type: str,
        target_id: str,
        is_read: bool | None,
        query: str,
    ) -> list[NotificationDelivery]:
        deliveries = sorted(self._load_deliveries(), key=lambda delivery: delivery.created_at, reverse=True)
        normalized_target_type = target_type.strip().lower()
        normalized_target_id = target_id.strip()
        needle = query.strip().lower()
        if rule_id:
            deliveries = [delivery for delivery in deliveries if delivery.rule_id == rule_id]
        if status:
            deliveries = [delivery for delivery in deliveries if delivery.status == status]
        if channel:
            deliveries = [delivery for delivery in deliveries if delivery.channel == channel]
        if normalized_target_type:
            deliveries = [
                delivery for delivery in deliveries if delivery.target_type.lower() == normalized_target_type
            ]
        if normalized_target_id:
            deliveries = [delivery for delivery in deliveries if delivery.target_id == normalized_target_id]
        if is_read is not None:
            deliveries = [
                delivery for delivery in deliveries if self._is_delivery_read(delivery) is is_read
            ]
        if needle:
            deliveries = [delivery for delivery in deliveries if needle in self._delivery_search_text(delivery)]
        return deliveries

    def _is_delivery_read(self, delivery: NotificationDelivery) -> bool:
        inbox = delivery.payload_json.get("_inbox")
        return isinstance(inbox, dict) and bool(inbox.get("read_at"))

    def _delivery_search_text(self, delivery: NotificationDelivery) -> str:
        return " ".join(
            [
                delivery.id,
                delivery.rule_id,
                delivery.target_type,
                delivery.target_id,
                delivery.channel.value,
                delivery.status.value,
                delivery.error_message,
                json.dumps(delivery.payload_json, ensure_ascii=False, sort_keys=True),
            ]
        ).lower()

    def _load_model_list(self, path: Path, model_class):
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        items = []
        for item in raw if isinstance(raw, list) else []:
            try:
                items.append(model_class.model_validate(item))
            except Exception:
                continue
        return items

    def _save_rules(self, rules: list[NotificationRule]) -> None:
        self._save_model_list(self.rules_file, rules)

    def _save_deliveries(self, deliveries: list[NotificationDelivery]) -> None:
        self._save_model_list(self.deliveries_file, deliveries)

    def _save_model_list(self, path: Path, items: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
