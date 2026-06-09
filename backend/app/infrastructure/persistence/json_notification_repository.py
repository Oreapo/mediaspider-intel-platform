from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.notification import NotificationDelivery, NotificationRule
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

    def list_deliveries(self) -> list[NotificationDelivery]:
        return sorted(self._load_deliveries(), key=lambda delivery: delivery.created_at, reverse=True)

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
