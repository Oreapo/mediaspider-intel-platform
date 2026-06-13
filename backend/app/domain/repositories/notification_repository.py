from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationRule,
)


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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def get_delivery(self, delivery_id: str) -> NotificationDelivery | None:
        raise NotImplementedError

    @abstractmethod
    def save_delivery(self, delivery: NotificationDelivery) -> NotificationDelivery:
        raise NotImplementedError
