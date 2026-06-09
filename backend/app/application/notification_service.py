from __future__ import annotations

import json
import smtplib
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
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

    def list_inbox(
        self,
        *,
        unread_only: bool = False,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        deliveries = [
            delivery
            for delivery in self.search_deliveries(
                status=NotificationDeliveryStatus.SENT,
                channel=NotificationChannel.INTERNAL_INBOX,
                query=query,
            )
            if not unread_only or not self._is_delivery_read(delivery)
        ]
        total = len(deliveries)
        unread_count = sum(
            1
            for delivery in self.search_deliveries(
                status=NotificationDeliveryStatus.SENT,
                channel=NotificationChannel.INTERNAL_INBOX,
            )
            if not self._is_delivery_read(delivery)
        )
        if offset:
            deliveries = deliveries[offset:]
        if limit is not None:
            deliveries = deliveries[:limit]
        return {
            "items": [self._inbox_item(delivery) for delivery in deliveries],
            "total": total,
            "unread_count": unread_count,
        }

    def update_inbox_item(self, delivery_id: str, read: bool = True) -> dict[str, Any]:
        delivery = self._get_delivery(delivery_id)
        if delivery is None or delivery.channel != NotificationChannel.INTERNAL_INBOX:
            raise ValueError(f"Inbox item {delivery_id} not found")
        metadata = dict(delivery.payload_json.get("_inbox") or {})
        if read:
            metadata["read_at"] = datetime.utcnow().isoformat()
        else:
            metadata.pop("read_at", None)
        payload = {**delivery.payload_json, "_inbox": metadata}
        updated = delivery.model_copy(update={"payload_json": payload, "updated_at": datetime.utcnow()})
        return self._inbox_item(self.repository.save_delivery(updated))

    def mark_all_inbox_read(self) -> dict[str, Any]:
        count = 0
        for delivery in self.repository.list_deliveries():
            if delivery.channel != NotificationChannel.INTERNAL_INBOX or self._is_delivery_read(delivery):
                continue
            self.update_inbox_item(delivery.id, read=True)
            count += 1
        return {"updated_count": count}

    def retry_delivery(self, delivery_id: str) -> NotificationDelivery:
        delivery = self._get_delivery(delivery_id)
        if delivery is None:
            raise ValueError(f"Notification delivery {delivery_id} not found")
        if delivery.status != NotificationDeliveryStatus.FAILED:
            raise ValueError("Only failed deliveries can be retried")
        rule = self.repository.get_rule(delivery.rule_id)
        if rule is None:
            raise ValueError(f"Notification rule {delivery.rule_id} not found")

        attempted_at = datetime.utcnow().isoformat()
        retry_count = delivery.retry_count + 1
        try:
            if delivery.channel == NotificationChannel.WEBHOOK:
                self._send_webhook(rule, delivery.payload_json)
            elif delivery.channel == NotificationChannel.EMAIL:
                self._send_email(rule, delivery.payload_json)
            elif delivery.channel == NotificationChannel.INTERNAL_INBOX:
                self._send_internal_inbox(rule, delivery.payload_json)
            updated = delivery.model_copy(
                update={
                    "status": NotificationDeliveryStatus.SENT,
                    "error_message": "",
                    "retry_count": retry_count,
                    "last_attempt_at": attempted_at,
                    "updated_at": datetime.utcnow(),
                }
            )
        except Exception as exc:
            updated = delivery.model_copy(
                update={
                    "error_message": str(exc),
                    "retry_count": retry_count,
                    "last_attempt_at": attempted_at,
                    "updated_at": datetime.utcnow(),
                }
            )
        return self.repository.save_delivery(updated)

    def search_deliveries(
        self,
        *,
        rule_id: str | None = None,
        status: NotificationDeliveryStatus | None = None,
        channel: NotificationChannel | None = None,
        target_type: str = "",
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NotificationDelivery]:
        deliveries = self.repository.list_deliveries()
        normalized_query = query.strip().lower()
        normalized_target_type = target_type.strip().lower()

        filtered: list[NotificationDelivery] = []
        for delivery in deliveries:
            if rule_id and delivery.rule_id != rule_id:
                continue
            if status and delivery.status != status:
                continue
            if channel and delivery.channel != channel:
                continue
            if normalized_target_type and delivery.target_type.lower() != normalized_target_type:
                continue
            if normalized_query and normalized_query not in self._delivery_search_text(delivery):
                continue
            filtered.append(delivery)

        if offset:
            filtered = filtered[offset:]
        if limit is not None:
            filtered = filtered[:limit]
        return filtered

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
            last_attempt_at=datetime.utcnow().isoformat(),
        )
        return self.repository.save_delivery(delivery)

    def _get_delivery(self, delivery_id: str) -> NotificationDelivery | None:
        for delivery in self.repository.list_deliveries():
            if delivery.id == delivery_id:
                return delivery
        return None

    def _is_delivery_read(self, delivery: NotificationDelivery) -> bool:
        inbox = delivery.payload_json.get("_inbox")
        return isinstance(inbox, dict) and bool(inbox.get("read_at"))

    def _inbox_item(self, delivery: NotificationDelivery) -> dict[str, Any]:
        payload = delivery.payload_json
        events = payload.get("events") if isinstance(payload, dict) else []
        event_count = len(events) if isinstance(events, list) else int(payload.get("event_count") or 0)
        target_event = None
        if isinstance(events, list):
            target_event = next(
                (
                    event
                    for event in events
                    if isinstance(event, dict)
                    and event.get("target_type") == delivery.target_type
                    and event.get("target_id") == delivery.target_id
                ),
                None,
            )
        target_payload = target_event.get("payload") if isinstance(target_event, dict) else {}
        if not isinstance(target_payload, dict):
            target_payload = {}
        inbox = payload.get("_inbox") if isinstance(payload, dict) else {}
        read_at = inbox.get("read_at") if isinstance(inbox, dict) else None
        return {
            "id": delivery.id,
            "rule_id": delivery.rule_id,
            "rule_name": payload.get("rule_name", "") if isinstance(payload, dict) else "",
            "target_type": delivery.target_type,
            "target_id": delivery.target_id,
            "status": delivery.status.value,
            "read": bool(read_at),
            "read_at": read_at,
            "created_at": delivery.created_at.isoformat(),
            "event_count": event_count,
            "title": self._notification_title(delivery, target_payload),
            "summary": self._notification_summary(delivery, target_payload),
            "payload_json": payload,
        }

    def _notification_title(self, delivery: NotificationDelivery, target_payload: dict[str, Any]) -> str:
        if delivery.target_type == "signal":
            return str(target_payload.get("summary") or f"风险信号 {delivery.target_id}")
        if delivery.target_type == "case":
            case = target_payload.get("case") if isinstance(target_payload.get("case"), dict) else target_payload
            return str(case.get("case_name") or f"案件 {delivery.target_id}")
        if delivery.target_type == "evidence_packet":
            return str(target_payload.get("packet_name") or f"证据包 {delivery.target_id}")
        return f"{delivery.target_type} {delivery.target_id}"

    def _notification_summary(self, delivery: NotificationDelivery, target_payload: dict[str, Any]) -> str:
        if delivery.target_type == "signal":
            return f"{target_payload.get('risk_level', '-')} · {target_payload.get('signal_type', '-')}"
        if delivery.target_type == "case":
            case = target_payload.get("case") if isinstance(target_payload.get("case"), dict) else target_payload
            return f"{case.get('status', '-')} · {case.get('priority', '-')}"
        if delivery.target_type == "evidence_packet":
            return str(target_payload.get("storage_uri") or "")
        return ""

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

    def _send_internal_inbox(self, rule: NotificationRule, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict) or "events" not in payload:
            raise ValueError("Invalid internal inbox payload")

    def _send_email(self, rule: NotificationRule, payload: dict[str, Any]) -> None:
        recipients = rule.channel_config_json.get("email_recipients") or []
        if not recipients:
            raise ValueError("email channel requires channel_config_json.email_recipients")
        smtp_host = rule.channel_config_json.get("smtp_host")
        if not smtp_host:
            raise ValueError("email channel requires channel_config_json.smtp_host")
        smtp_port = int(rule.channel_config_json.get("smtp_port") or 25)
        sender = rule.channel_config_json.get("smtp_from") or rule.channel_config_json.get("smtp_username")
        if not sender:
            raise ValueError("email channel requires channel_config_json.smtp_from")
        if isinstance(recipients, str):
            recipients = [item.strip() for item in recipients.split(",") if item.strip()]
        if not isinstance(recipients, list) or not all(isinstance(item, str) and item.strip() for item in recipients):
            raise ValueError("email channel email_recipients must be a list of email addresses")

        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = self._email_subject(rule, payload)
        message.set_content(self._email_body(payload))

        timeout = int(rule.channel_config_json.get("smtp_timeout_seconds") or 10)
        use_tls = bool(rule.channel_config_json.get("smtp_use_tls", False))
        username = rule.channel_config_json.get("smtp_username")
        password = rule.channel_config_json.get("smtp_password")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)

    def _email_subject(self, rule: NotificationRule, payload: dict[str, Any]) -> str:
        count = int(payload.get("event_count") or 0)
        return f"[MediaSpider] {rule.rule_name} · {count} events"

    def _email_body(self, payload: dict[str, Any]) -> str:
        lines = [
            "MediaSpider intelligence digest",
            "",
            f"Rule: {payload.get('rule_name', '-')}",
            f"Window: {payload.get('since', '-')} -> {payload.get('until', '-')}",
            f"Events: {payload.get('event_count', 0)}",
            "",
        ]
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        for index, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                continue
            target_type = event.get("target_type", "-")
            target_id = event.get("target_id", "-")
            item = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            title = self._event_title(str(target_type), item)
            lines.append(f"{index}. {target_type}/{target_id} - {title}")
        return "\n".join(lines).strip() + "\n"

    def _event_title(self, target_type: str, payload: dict[str, Any]) -> str:
        if target_type == "signal":
            return str(payload.get("summary") or payload.get("signal_type") or "risk signal")
        if target_type == "case":
            case = payload.get("case") if isinstance(payload.get("case"), dict) else payload
            return str(case.get("case_name") or "case")
        if target_type == "evidence_packet":
            return str(payload.get("packet_name") or "evidence packet")
        return str(payload.get("id") or "event")

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
