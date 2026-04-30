from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.notification import NotificationDelivery, NotificationRule


class NotificationRepository(ABC):
    @abstractmethod
    def list_rules(self) -> list[NotificationRule]:
        raise NotImplementedError

    @abstractmethod
    def get_rule(self, rule_id: str) -> NotificationRule | None:
        raise NotImplementedError

    @abstractmethod
    def save_rule(self, rule: NotificationRule) -> NotificationRule:
        raise NotImplementedError

    @abstractmethod
    def delete_rule(self, rule_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_deliveries(self) -> list[NotificationDelivery]:
        raise NotImplementedError

    @abstractmethod
    def save_delivery(self, delivery: NotificationDelivery) -> NotificationDelivery:
        raise NotImplementedError
