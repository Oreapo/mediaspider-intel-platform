from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from ..api.schemas.notification import NotificationRuleCreateRequest, NotificationRuleUpdateRequest
from ..domain.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationEventType,
    NotificationRule,
)
from ..domain.models.signal import RiskLevel
from ..domain.repositories.notification_repository import NotificationRepository
from .case_service import CaseService
from .dataset_service import DatasetService
from .evidence_service import EvidenceService
from .signal_service import SignalService


class NotificationService:
    RISK_ORDER = {
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
        RiskLevel.CRITICAL: 4,
    }

    def __init__(
        self,
        repository: NotificationRepository,
        signal_service: SignalService,
        case_service: CaseService,
        evidence_service: EvidenceService,
        dataset_service: DatasetService,
    ):
        self.repository = repository
        self.signal_service = signal_service
        self.case_service = case_service
        self.evidence_service = evidence_service
        self.dataset_service = dataset_service

    def list_rules(self) -> list[NotificationRule]:
        return self.repository.list_rules()

    def get_rule(self, rule_id: str) -> NotificationRule | None:
        return self.repository.get_rule(rule_id)

    def create_rule(self, payload: NotificationRuleCreateRequest) -> NotificationRule:
        rule = NotificationRule(**payload.model_dump())
        self._validate_rule(rule)
        return self.repository.save_rule(rule)

    def update_rule(self, rule_id: str, payload: NotificationRuleUpdateRequest) -> NotificationRule:
        rule = self.repository.get_rule(rule_id)
        if rule is None:
            raise ValueError(f"Notification rule {rule_id} not found")
        updated = rule.model_copy(
            update={
                **payload.model_dump(exclude_unset=True),
                "updated_at": datetime.utcnow(),
            }
        )
        self._validate_rule(updated)
        return self.repository.save_rule(updated)

    def delete_rule(self, rule_id: str) -> bool:
        return self.repository.delete_rule(rule_id)

    def list_deliveries(self) -> list[NotificationDelivery]:
        return self.repository.list_deliveries()

    def run_scheduled_digests(self, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.utcnow()
        results: list[dict[str, Any]] = []
        for rule in self.repository.list_rules():
            if not rule.enabled or rule.event_type != NotificationEventType.SCHEDULED_DIGEST:
                continue
            if not self._is_due(rule, current):
                continue
            since = self._parse_datetime(rule.last_executed_at) or datetime.min
            events = self._collect_events(rule, since)
            deliveries: list[NotificationDelivery] = []
            if not events:
                deliveries.append(
                    self._record_delivery(
                        rule=rule,
                        target_type="scheduled_digest",
                        target_id=f"digest:{current.isoformat()}",
                        channel=NotificationChannel.INTERNAL_INBOX,
                        status=NotificationDeliveryStatus.SKIPPED,
                        payload={"reason": "no_matching_events", "since": since.isoformat()},
                    )
                )
            else:
                payload = self._digest_payload(rule, events, since, current)
                for channel in rule.channels:
                    deliveries.extend(self._deliver(rule, channel, payload, events))
            saved_rule = rule.model_copy(
                update={
                    "last_executed_at": current.isoformat(),
                    "updated_at": datetime.utcnow(),
                }
            )
            self.repository.save_rule(saved_rule)
            results.append(
                {
                    "rule_id": rule.id,
                    "event_count": len(events),
                    "delivery_count": len(deliveries),
                    "deliveries": [delivery.model_dump(mode="json") for delivery in deliveries],
                }
            )
        return {"ran_at": current.isoformat(), "results": results}

    def _validate_rule(self, rule: NotificationRule) -> None:
        self._parse_cron(rule.cron_expr)
        if not rule.channels:
            raise ValueError("Notification rule must have at least one channel")

    def _is_due(self, rule: NotificationRule, now: datetime) -> bool:
        if not self._cron_matches(rule.cron_expr, now):
            return False
        last = self._parse_datetime(rule.last_executed_at)
        current_minute = now.replace(second=0, microsecond=0)
        return last is None or last.replace(second=0, microsecond=0) < current_minute

    def _collect_events(self, rule: NotificationRule, since: datetime) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for signal in self.signal_service.list_signals():
            if signal.created_at <= since or not self._signal_matches(rule, signal.model_dump(mode="json")):
                continue
            if self._is_in_cooldown(rule, "signal", signal.id):
                continue
            events.append({"target_type": "signal", "target_id": signal.id, "payload": signal.model_dump(mode="json")})

        for case in self.case_service.list_cases():
            detail = self.case_service.get_case_detail(case.id)
            if case.updated_at <= since or detail is None or not self._case_matches(rule, detail):
                continue
            if self._is_in_cooldown(rule, "case", case.id):
                continue
            events.append({"target_type": "case", "target_id": case.id, "payload": detail})

        for packet in self.evidence_service.list_packets():
            case_detail = self.case_service.get_case_detail(packet.case_id)
            if packet.created_at <= since or case_detail is None or not self._case_matches(rule, case_detail):
                continue
            if self._is_in_cooldown(rule, "evidence_packet", packet.id):
                continue
            events.append(
                {
                    "target_type": "evidence_packet",
                    "target_id": packet.id,
                    "payload": packet.model_dump(mode="json"),
                }
            )
        return sorted(events, key=lambda item: (item["target_type"], item["target_id"]))

    def _signal_matches(self, rule: NotificationRule, signal: dict[str, Any]) -> bool:
        dataset = self.dataset_service.get_dataset(signal["dataset_id"])
        platform = dataset.source_platform.value if dataset is not None else None
        scenario = dataset.scenario_type.value if dataset is not None and dataset.scenario_type else None
        return (
            self._risk_allowed(rule, signal.get("risk_level"))
            and self._platform_allowed(rule, platform)
            and self._scenario_allowed(rule, scenario)
        )

    def _case_matches(self, rule: NotificationRule, detail: dict[str, Any]) -> bool:
        case = detail["case"]
        platforms = {
            dataset.get("source_platform")
            for dataset in detail["objects"]["datasets"]
            if dataset.get("source_platform")
        }
        signal_levels = [signal.get("risk_level") for signal in detail["objects"]["signals"]]
        return (
            self._scenario_allowed(rule, case.get("case_type"))
            and self._platforms_allowed(rule, platforms)
            and self._risk_collection_allowed(rule, signal_levels)
        )

    def _risk_allowed(self, rule: NotificationRule, risk_level: str | None) -> bool:
        if risk_level is None:
            return rule.risk_level_threshold == RiskLevel.LOW
        try:
            level = RiskLevel(risk_level)
        except ValueError:
            return False
        return self.RISK_ORDER[level] >= self.RISK_ORDER[rule.risk_level_threshold]

    def _risk_collection_allowed(self, rule: NotificationRule, risk_levels: list[str | None]) -> bool:
        if not risk_levels:
            return rule.risk_level_threshold == RiskLevel.LOW
        return any(self._risk_allowed(rule, level) for level in risk_levels)

    def _scenario_allowed(self, rule: NotificationRule, scenario: str | None) -> bool:
        return not rule.scenario_types or (scenario is not None and scenario in rule.scenario_types)

    def _platform_allowed(self, rule: NotificationRule, platform: str | None) -> bool:
        return not rule.platforms or (platform is not None and platform in rule.platforms)

    def _platforms_allowed(self, rule: NotificationRule, platforms: set[str]) -> bool:
        return not rule.platforms or bool(platforms & set(rule.platforms))

    def _is_in_cooldown(self, rule: NotificationRule, target_type: str, target_id: str) -> bool:
        if rule.cooldown_minutes <= 0:
            return False
        cutoff = datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes)
        for delivery in self.repository.list_deliveries():
            if delivery.rule_id != rule.id or delivery.target_type != target_type or delivery.target_id != target_id:
                continue
            if delivery.status != NotificationDeliveryStatus.SENT:
                continue
            if delivery.created_at >= cutoff:
                return True
        return False

    def _digest_payload(
        self,
        rule: NotificationRule,
        events: list[dict[str, Any]],
        since: datetime,
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "rule_id": rule.id,
            "rule_name": rule.rule_name,
            "event_type": rule.event_type.value,
            "since": since.isoformat(),
            "until": now.isoformat(),
            "event_count": len(events),
            "events": events,
        }

    def _deliver(
        self,
        rule: NotificationRule,
        channel: NotificationChannel,
        payload: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> list[NotificationDelivery]:
        try:
            if channel == NotificationChannel.WEBHOOK:
                self._send_webhook(rule, payload)
            elif channel == NotificationChannel.EMAIL:
                self._send_email(rule, payload)
            elif channel == NotificationChannel.INTERNAL_INBOX:
                self._send_internal_inbox(rule, payload)
            return [
                self._record_delivery(
                    rule=rule,
                    target_type=event["target_type"],
                    target_id=event["target_id"],
                    channel=channel,
                    status=NotificationDeliveryStatus.SENT,
                    payload=payload,
                )
                for event in events
            ]
        except Exception as exc:
            return [
                self._record_delivery(
                    rule=rule,
                    target_type=event["target_type"],
                    target_id=event["target_id"],
                    channel=channel,
                    status=NotificationDeliveryStatus.FAILED,
                    payload=payload,
                    error_message=str(exc),
                )
                for event in events
            ]

    def _record_delivery(
        self,
        *,
        rule: NotificationRule,
        target_type: str,
        target_id: str,
        channel: NotificationChannel,
        status: NotificationDeliveryStatus,
        payload: dict[str, Any],
        error_message: str = "",
    ) -> NotificationDelivery:
        delivery = NotificationDelivery(
            rule_id=rule.id,
            target_type=target_type,
            target_id=target_id,
            channel=channel,
            status=status,
            payload_json=payload,
            error_message=error_message,
        )
        return self.repository.save_delivery(delivery)

    def _send_internal_inbox(self, rule: NotificationRule, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict) or "events" not in payload:
            raise ValueError("Invalid internal inbox payload")

    def _send_email(self, rule: NotificationRule, payload: dict[str, Any]) -> None:
        recipients = rule.channel_config_json.get("email_recipients") or []
        if not recipients:
            raise ValueError("email channel requires channel_config_json.email_recipients")

    def _send_webhook(self, rule: NotificationRule, payload: dict[str, Any]) -> None:
        url = rule.channel_config_json.get("webhook_url")
        if not url:
            raise ValueError("webhook channel requires channel_config_json.webhook_url")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status >= 400:
                    raise ValueError(f"webhook returned HTTP {response.status}")
        except urllib.error.URLError as exc:
            raise ValueError(f"webhook delivery failed: {exc}") from exc

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    def _parse_cron(self, cron_expr: str) -> list[str]:
        fields = cron_expr.split()
        if len(fields) != 5:
            raise ValueError("cron_expr must contain five fields")
        return fields

    def _cron_matches(self, cron_expr: str, now: datetime) -> bool:
        minute, hour, day, month, weekday = self._parse_cron(cron_expr)
        return (
            self._field_matches(minute, now.minute, 0, 59)
            and self._field_matches(hour, now.hour, 0, 23)
            and self._field_matches(day, now.day, 1, 31)
            and self._field_matches(month, now.month, 1, 12)
            and self._field_matches(weekday, now.weekday(), 0, 6)
        )

    def _field_matches(self, field: str, value: int, minimum: int, maximum: int) -> bool:
        for part in field.split(","):
            if part == "*":
                return True
            if part.startswith("*/"):
                step = int(part[2:])
                if step <= 0:
                    raise ValueError("cron step must be positive")
                if value % step == 0:
                    return True
                continue
            if "-" in part:
                start, end = [int(item) for item in part.split("-", 1)]
                if start <= value <= end:
                    return True
                continue
            number = int(part)
            if number < minimum or number > maximum:
                raise ValueError("cron field value out of range")
            if value == number:
                return True
        return False
