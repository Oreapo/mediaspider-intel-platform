from __future__ import annotations

import json
import re
import statistics
import unicodedata
from datetime import datetime, timezone
from typing import Any

from ..api.schemas.signal import SignalCreateRequest
from ..domain.models.signal import RiskLevel, Signal, SignalStatus, SignalType
from ..domain.repositories.signal_repository import SignalRepository
from .dataset_service import DatasetService


class SignalService:
    CONTACT_PATTERN = re.compile(
        r"(?:微信|vx|v信|qq|QQ|手机|电话|telegram|tg|群|加我|私信)[：:\s-]*([A-Za-z0-9_\-]{5,})",
        re.IGNORECASE,
    )
    # Invisible characters black/grey actors splice into keywords to evade
    # naive substring matching (zero-width joiners, BOM, word joiner, etc.).
    _ZERO_WIDTH = re.compile(r"[​‌‍‎‏⁠﻿]")
    # Everything that is not CJK or an ASCII alphanumeric — the separators
    # used to break up a term (spaces, punctuation, symbols, emoji).
    _NON_TOKEN = re.compile(r"[^0-9a-z一-鿿]+")
    # Homophone / look-alike spellings used to dodge keyword rules, mapped to
    # their canonical form. Deliberately phrase-level and conservative (not a
    # single-character homophone table) so legitimate words are not rewritten.
    # Keys are already lowercase/collapsed. Extend as new variants are observed.
    _VARIANT_ALIASES = {
        "微信": ("薇信", "徽信", "溦信"),
        "qq": ("扣扣", "抠抠"),
        "引流": ("引留",),
    }
    RISK_TERMS = {
        "引流": RiskLevel.HIGH,
        "兼职": RiskLevel.MEDIUM,
        "招募": RiskLevel.MEDIUM,
        "刷单": RiskLevel.HIGH,
        "养号": RiskLevel.HIGH,
        "接码": RiskLevel.HIGH,
        "代实名": RiskLevel.HIGH,
        "灰产": RiskLevel.CRITICAL,
        "黑产": RiskLevel.CRITICAL,
        "私域": RiskLevel.MEDIUM,
        "站外": RiskLevel.MEDIUM,
        "薅羊毛": RiskLevel.MEDIUM,
    }
    # Black/grey-industry recruitment signal: requires an intent term AND an
    # incentive cue to co-occur, which is far more precise than a single keyword.
    RECRUIT_INTENT_TERMS = (
        "招募",
        "诚招",
        "急招",
        "招代理",
        "招学员",
        "收徒",
        "带做",
        "带飞",
        "扩招",
        "招兼职",
        "长期有效",
    )
    RECRUIT_INCENTIVE_TERMS = (
        "日结",
        "佣金",
        "提成",
        "月入",
        "日入",
        "包教",
        "包会",
        "无门槛",
        "门槛低",
        "在家",
        "手机操作",
        "时间自由",
        "上不封顶",
        "返现",
    )
    # Black/grey-industry tool/service trafficking: an offer noun (tool/service)
    # co-occurring with a trade cue (selling / supply / on-demand).
    SERVICE_OFFER_TERMS = (
        "外挂",
        "脚本",
        "群控",
        "协议号",
        "接码",
        "打码",
        "解封",
        "代过",
        "卡密",
        "发卡",
        "号商",
        "代充",
        "爆粉",
        "秒拨",
        "虚拟号",
        "采集软件",
        "引流软件",
    )
    SERVICE_TRADE_TERMS = (
        "出售",
        "出货",
        "卖",
        "有货",
        "秒发",
        "接单",
        "承接",
        "批发",
        "供应",
        "一手",
        "低价",
        "质保",
        "技术支持",
    )
    # Off-platform / private-domain traffic routing: a guiding action co-occurring
    # with an off-platform landing target.
    TRAFFIC_ACTION_TERMS = (
        "加我",
        "扫码",
        "扫一扫",
        "私信",
        "点主页",
        "看主页",
        "置顶",
        "评论区",
        "进群",
        "加群",
        "戳我",
        "关注公众号",
    )
    TRAFFIC_LANDING_TERMS = (
        "微信",
        "vx",
        "v信",
        "公众号",
        "电报",
        "telegram",
        "tg",
        "站外",
        "二维码",
        "网址",
        "链接",
    )
    TEXT_FIELDS = (
        "title",
        "desc",
        "body",
        "content",
        "text",
        "comment",
        "comment_text",
        "caption",
        "subtitle",
        "ocr_text",
        "asr_text",
        "product_title",
        "product_desc",
    )
    LEAD_DIVERSION_TERMS = (
        "私信",
        "主页",
        "评论区",
        "置顶",
        "加我",
        "加微",
        "进群",
        "群里",
        "领取",
        "资料",
        "教程",
        "完整流程",
    )
    DY_SCRIPT_FIELDS = ("caption", "desc", "subtitle", "ocr_text", "asr_text", "title")

    def __init__(self, repository: SignalRepository, dataset_service: DatasetService):
        self.repository = repository
        self.dataset_service = dataset_service

    def list_signals(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Signal]:
        return self.repository.list_signals(
            dataset_id=dataset_id,
            status=status,
            risk_level=risk_level,
            signal_type=signal_type,
            query=query,
            limit=limit,
            offset=offset,
        )

    def list_signals_page(
        self,
        *,
        dataset_id: str | None = None,
        status: SignalStatus | None = None,
        risk_level: RiskLevel | None = None,
        signal_type: SignalType | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Signal], int]:
        filters = {
            "dataset_id": dataset_id,
            "status": status,
            "risk_level": risk_level,
            "signal_type": signal_type,
            "query": query,
        }
        return (
            self.repository.list_signals(**filters, limit=limit, offset=offset),
            self.repository.count_signals(**filters),
        )

    def get_signal(self, signal_id: str) -> Signal | None:
        return self.repository.get_signal(signal_id)

    def create_signal(self, payload: SignalCreateRequest) -> Signal:
        dataset = self.dataset_service.get_dataset(payload.dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {payload.dataset_id} not found")
        signal = Signal(**payload.model_dump())
        return self.repository.save_signal(signal)

    def update_status(self, signal_id: str, status: SignalStatus) -> Signal:
        signal = self.repository.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"Signal {signal_id} not found")
        updated = signal.model_copy(update={"status": status, "updated_at": datetime.utcnow()})
        return self.repository.save_signal(updated)

    def delete_signal(self, signal_id: str) -> bool:
        return self.repository.delete_signal(signal_id)

    def delete_signals_for_dataset(self, dataset_id: str) -> int:
        return self.repository.delete_signals_for_dataset(dataset_id)

    def cluster_by_contact(self, dataset_id: str) -> list[dict[str, Any]]:
        """Group a dataset's signals by shared contact point into candidate gangs.

        Signals that expose the same ``payload_json.contact_point`` are collected
        into one cluster — the seed for a gang (团伙) entity. Clusters are ordered
        by size then peak risk so the most significant candidates surface first.
        """
        buckets: dict[str, list[Signal]] = {}
        for signal in self.repository.list_signals(dataset_id=dataset_id):
            contact = signal.payload_json.get("contact_point")
            if not isinstance(contact, str) or not contact.strip():
                continue
            buckets.setdefault(contact.strip(), []).append(signal)

        clusters: list[dict[str, Any]] = []
        for contact, members in buckets.items():
            risk_levels: dict[str, int] = {}
            for member in members:
                key = member.risk_level.value
                risk_levels[key] = risk_levels.get(key, 0) + 1
            clusters.append(
                {
                    "contact_point": contact,
                    "signal_ids": [str(member.id) for member in members],
                    "signal_count": len(members),
                    "risk_levels": risk_levels,
                    "max_risk_score": max((member.risk_score for member in members), default=0),
                }
            )
        clusters.sort(key=lambda cluster: (cluster["signal_count"], cluster["max_risk_score"]), reverse=True)
        return clusters

    def cluster_gangs(self, dataset_id: str) -> list[dict[str, Any]]:
        """Cluster a dataset's signals into candidate gangs by relationship graph.

        Builds an undirected graph whose nodes are signals and whose edges join
        signals that share **any** identifier — a contact point, a reused
        content/seller template, or an author id — then returns the connected
        components (communities) with at least two signals. Transitivity means a
        gang using several rotating contacts but one reused script (A—contact—B,
        B—template—C) is surfaced as a single cluster, which pure contact
        grouping misses. Ordered by size then peak risk.
        """
        signals = self.repository.list_signals(dataset_id=dataset_id)
        parent = list(range(len(signals)))

        def find(node: int) -> int:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        signal_keys: list[set[tuple[str, str]]] = []
        key_to_signals: dict[tuple[str, str], list[int]] = {}
        for index, signal in enumerate(signals):
            keys = self._gang_link_keys(signal)
            signal_keys.append(keys)
            for key in keys:
                key_to_signals.setdefault(key, []).append(index)

        for members in key_to_signals.values():
            for other in members[1:]:
                union(members[0], other)

        components: dict[int, list[int]] = {}
        for index in range(len(signals)):
            components.setdefault(find(index), []).append(index)

        clusters: list[dict[str, Any]] = []
        for members in components.values():
            if len(members) < 2:
                continue
            member_signals = [signals[index] for index in members]
            shared_keys = set()
            for index in members:
                shared_keys |= {key for key in signal_keys[index] if len(key_to_signals[key]) >= 2}
            contacts = sorted({value for kind, value in shared_keys if kind == "contact"})
            link_types = sorted({kind for kind, _ in shared_keys})
            risk_levels: dict[str, int] = {}
            for member in member_signals:
                risk_levels[member.risk_level.value] = risk_levels.get(member.risk_level.value, 0) + 1
            platforms = sorted(
                {
                    str(platform)
                    for member in member_signals
                    if isinstance(member.payload_json.get("source_ref"), dict)
                    for platform in [member.payload_json["source_ref"].get("source_platform")]
                    if platform
                }
            )
            clusters.append(
                {
                    "cluster_key": min(str(member.id) for member in member_signals),
                    "label": self._gang_label(contacts, link_types),
                    "link_types": link_types,
                    "contact_point": contacts[0] if contacts else "",
                    "contact_points": contacts,
                    "platforms": platforms,
                    "signal_ids": [str(member.id) for member in member_signals],
                    "signal_count": len(member_signals),
                    "risk_levels": risk_levels,
                    "max_risk_score": max((member.risk_score for member in member_signals), default=0),
                }
            )
        clusters.sort(key=lambda cluster: (cluster["signal_count"], cluster["max_risk_score"]), reverse=True)
        return clusters

    def _gang_link_keys(self, signal: Signal) -> set[tuple[str, str]]:
        """Identifiers that tie a signal to others in the same gang."""
        payload = signal.payload_json
        keys: set[tuple[str, str]] = set()

        contact = payload.get("contact_point")
        if isinstance(contact, str) and contact.strip():
            keys.add(("contact", contact.strip().lower()))
        for contact in payload.get("contact_points") or []:
            if isinstance(contact, str) and contact.strip():
                keys.add(("contact", contact.strip().lower()))

        for field in ("template_key", "seller_template_key"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                keys.add(("template", value.strip()))

        for user in payload.get("user_ids") or []:
            if user is not None and str(user).strip():
                keys.add(("account", str(user).strip()))

        return keys

    def detect_activity_bursts(self, dataset_id: str, *, limit: int = 2000) -> dict[str, Any]:
        """Detect abnormal spikes in a dataset's posting activity over time.

        Resolves a calendar day for each record, counts posts per day, then
        flags days whose volume stands out against the dataset's own baseline
        (mean + 2·σ, with a small absolute floor to avoid noise on tiny sets).
        A burst is the temporal fingerprint of a coordinated black/grey campaign
        — many accounts pushing the same thing in a narrow window.
        """
        dataset = self.dataset_service.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        preview = self.dataset_service.preview_dataset(dataset_id, limit=limit)
        columns = [str(column) for column in preview.get("columns", [])]
        per_day: dict[str, int] = {}
        for row in preview.get("rows", []):
            record = dict(zip(columns, row))
            day = self._resolve_day(record)
            if day:
                per_day[day] = per_day.get(day, 0) + 1

        counts = list(per_day.values())
        total = sum(counts)
        mean = statistics.fmean(counts) if counts else 0.0
        stdev = statistics.pstdev(counts) if len(counts) > 1 else 0.0
        threshold = mean + 2 * stdev

        buckets: list[dict[str, Any]] = []
        for day in sorted(per_day):
            count = per_day[day]
            is_burst = bool(count >= 3 and stdev > 0 and count >= threshold)
            buckets.append(
                {
                    "date": day,
                    "count": count,
                    "ratio": round(count / mean, 2) if mean else 0.0,
                    "is_burst": is_burst,
                }
            )

        bursts = sorted(
            (bucket for bucket in buckets if bucket["is_burst"]),
            key=lambda bucket: bucket["count"],
            reverse=True,
        )
        return {
            "total_records": total,
            "day_count": len(buckets),
            "baseline": round(mean, 2),
            "threshold": round(threshold, 2),
            "buckets": buckets,
            "bursts": bursts,
        }

    def _resolve_day(self, record: dict[str, Any]) -> str | None:
        """Best-effort calendar day (YYYY-MM-DD) from a record's time fields."""
        for field in (
            "publish_time",
            "published_at",
            "publish_ts",
            "create_time",
            "created_time",
            "created_at",
            "add_ts",
            "last_modify_ts",
            "timestamp",
            "time",
            "date",
        ):
            if field in record and record[field] not in (None, ""):
                day = self._to_day(record[field])
                if day:
                    return day
        return None

    def _to_day(self, raw: Any) -> str | None:
        text = str(raw).strip()
        if not text:
            return None
        if text.isdigit():
            number = int(text)
            if number >= 10**15:  # microseconds
                number //= 1_000_000
            elif number >= 10**12:  # milliseconds
                number //= 1000
            if number < 10**9:  # implausible as a modern epoch second
                return None
            try:
                return datetime.fromtimestamp(number, tz=timezone.utc).strftime("%Y-%m-%d")
            except (ValueError, OSError, OverflowError):
                return None
        match = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                return None
        return None

    def _gang_label(self, contacts: list[str], link_types: list[str]) -> str:
        if contacts:
            label = contacts[0]
            if len(contacts) > 1:
                label += f" 等 {len(contacts)} 个联系方式"
            return label
        if "template" in link_types:
            return "文案模板复用团伙"
        if "account" in link_types:
            return "同账号关联团伙"
        return "关联团伙"

    def extract_from_dataset(
        self,
        *,
        dataset_id: str,
        extractors: list[str] | None = None,
        limit: int = 100,
        task_run_id: str | None = None,
    ) -> list[Signal]:
        dataset = self.dataset_service.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        enabled = set(extractors or ["risk_terms", "contact_points"])
        preview = self.dataset_service.preview_dataset(dataset_id, limit=limit)
        columns = [str(column) for column in preview.get("columns", [])]
        rows = preview.get("rows", [])
        dataset_platform = dataset.source_platform.value

        created: list[Signal] = []
        records: list[dict[str, Any]] = []
        for row_index, row in enumerate(rows):
            record = dict(zip(columns, row))
            records.append(record)
            text = self._record_text(record)
            if "risk_terms" in enabled:
                created.extend(self._extract_risk_terms(dataset_id, row_index, record, text, dataset_platform))
            if "recruit_pattern" in enabled:
                created.extend(self._extract_recruit_pattern(dataset_id, row_index, record, text, dataset_platform))
            if "service_offer" in enabled:
                created.extend(self._extract_service_offer(dataset_id, row_index, record, text, dataset_platform))
            if "traffic_route" in enabled:
                created.extend(self._extract_traffic_route(dataset_id, row_index, record, text, dataset_platform))
            if "contact_points" in enabled:
                created.extend(self._extract_contact_points(dataset_id, row_index, record, text, dataset_platform))

        if "template_similarity" in enabled:
            created.extend(self._extract_template_similarity(dataset_id, records, dataset_platform))
        if "abnormal_activity" in enabled:
            created.extend(self._extract_abnormal_activity(dataset_id, records, dataset_platform))
        if "seller_template_reuse" in enabled:
            created.extend(self._extract_seller_template_reuse(dataset_id, records, dataset_platform))
        if "abnormal_price_band" in enabled:
            created.extend(self._extract_abnormal_price_band(dataset_id, records, dataset_platform))
        if "xhs_comment_lead_diversion" in enabled:
            created.extend(self._extract_xhs_comment_lead_diversion(dataset_id, records, dataset_platform))
        if "dy_script_diversion" in enabled:
            created.extend(self._extract_dy_script_diversion(dataset_id, records, dataset_platform))
        if "wb_topic_propagation" in enabled:
            created.extend(self._extract_wb_topic_propagation(dataset_id, records, dataset_platform))

        if task_run_id:
            created = [
                signal.model_copy(update={"task_run_id": task_run_id})
                for signal in created
            ]

        existing_keys = {
            self._signal_dedupe_key(signal)
            for signal in self.repository.list_signals(dataset_id=dataset_id)
        }
        saved: list[Signal] = []
        for signal in created:
            dedupe_key = self._signal_dedupe_key(signal)
            if dedupe_key in existing_keys:
                continue
            existing_keys.add(dedupe_key)
            payload_json = {**signal.payload_json, "dedupe_key": dedupe_key}
            saved.append(self.repository.save_signal(signal.model_copy(update={"payload_json": payload_json})))
        return saved

    def _signal_dedupe_key(self, signal: Signal) -> str:
        existing_key = signal.payload_json.get("dedupe_key")
        if isinstance(existing_key, str) and existing_key.strip():
            return existing_key

        payload = signal.payload_json
        source_ref = payload.get("source_ref") if isinstance(payload.get("source_ref"), dict) else {}
        identity = {
            "dataset_id": signal.dataset_id,
            "signal_type": signal.signal_type.value,
            "signal_source": signal.signal_source,
            "row_index": payload.get("row_index") or source_ref.get("row_index"),
            "source_entity_id": source_ref.get("source_entity_id"),
            "raw_ref": source_ref.get("raw_ref"),
            "term": payload.get("term"),
            "contact_point": payload.get("contact_point"),
            "contact_points": payload.get("contact_points"),
            "lead_terms": payload.get("lead_terms"),
            "template_key": payload.get("template_key"),
            "seller_template_key": payload.get("seller_template_key"),
            "activity_key": payload.get("activity_key"),
            "propagation_key": payload.get("propagation_key"),
            "row_indexes": payload.get("row_indexes"),
            "user_ids": payload.get("user_ids"),
            "price": payload.get("price"),
            "original_price": payload.get("original_price"),
            "summary": signal.summary,
        }
        return json.dumps(identity, ensure_ascii=False, sort_keys=True, default=str)

    def _extract_risk_terms(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        text: str,
        dataset_platform: str,
    ) -> list[Signal]:
        signals: list[Signal] = []
        norm = self._collapse(text)
        for term, risk_level in self.RISK_TERMS.items():
            if term not in norm:
                continue
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.RISK_TERM_HIT,
                    signal_source="rule:risk_terms",
                    risk_level=risk_level,
                    risk_score=self._risk_score(risk_level),
                    summary=f"命中风险词：{term}",
                    payload_json={
                        "term": term,
                        "deobfuscated": term not in text,
                        "row_index": row_index,
                        "source_ref": self._source_ref(dataset_id, row_index, record, dataset_platform),
                        "record_excerpt": text[:240],
                    },
                )
            )
        return signals

    def _extract_recruit_pattern(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        text: str,
        dataset_platform: str,
    ) -> list[Signal]:
        norm = self._collapse(text)
        intents = [term for term in self.RECRUIT_INTENT_TERMS if term in norm]
        incentives = [term for term in self.RECRUIT_INCENTIVE_TERMS if term in norm]
        if not intents or not incentives:
            return []
        return [
            Signal(
                dataset_id=dataset_id,
                signal_type=SignalType.RECRUIT_PATTERN_HIT,
                signal_source="rule:recruit_pattern",
                risk_level=RiskLevel.HIGH,
                risk_score=self._risk_score(RiskLevel.HIGH),
                summary=f"疑似黑灰产招募话术：{intents[0]} + {incentives[0]}",
                payload_json={
                    "recruit_intent_terms": intents,
                    "recruit_incentive_terms": incentives,
                    "deobfuscated": any(term not in text for term in intents + incentives),
                    "row_index": row_index,
                    "source_ref": self._source_ref(dataset_id, row_index, record, dataset_platform),
                    "record_excerpt": text[:240],
                },
            )
        ]

    def _extract_service_offer(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        text: str,
        dataset_platform: str,
    ) -> list[Signal]:
        norm = self._collapse(text)
        offers = [term for term in self.SERVICE_OFFER_TERMS if term in norm]
        trades = [term for term in self.SERVICE_TRADE_TERMS if term in norm]
        if not offers or not trades:
            return []
        return [
            Signal(
                dataset_id=dataset_id,
                signal_type=SignalType.SERVICE_OFFER_HIT,
                signal_source="rule:service_offer",
                risk_level=RiskLevel.HIGH,
                risk_score=self._risk_score(RiskLevel.HIGH),
                summary=f"疑似黑灰产工具/服务兜售：{offers[0]} + {trades[0]}",
                payload_json={
                    "service_offer_terms": offers,
                    "service_trade_terms": trades,
                    "deobfuscated": any(term not in text for term in offers + trades),
                    "row_index": row_index,
                    "source_ref": self._source_ref(dataset_id, row_index, record, dataset_platform),
                    "record_excerpt": text[:240],
                },
            )
        ]

    def _extract_traffic_route(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        text: str,
        dataset_platform: str,
    ) -> list[Signal]:
        norm = self._collapse(text)
        actions = [term for term in self.TRAFFIC_ACTION_TERMS if term in norm]
        landings = [term for term in self.TRAFFIC_LANDING_TERMS if term in norm]
        if not actions or not landings:
            return []
        return [
            Signal(
                dataset_id=dataset_id,
                signal_type=SignalType.TRAFFIC_ROUTE_HIT,
                signal_source="rule:traffic_route",
                risk_level=RiskLevel.HIGH,
                risk_score=self._risk_score(RiskLevel.HIGH),
                summary=f"疑似站外/私域引流路径：{actions[0]} + {landings[0]}",
                payload_json={
                    "traffic_action_terms": actions,
                    "traffic_landing_terms": landings,
                    "deobfuscated": any(term not in text for term in actions + landings),
                    "row_index": row_index,
                    "source_ref": self._source_ref(dataset_id, row_index, record, dataset_platform),
                    "record_excerpt": text[:240],
                },
            )
        ]

    def _extract_contact_points(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        text: str,
        dataset_platform: str,
    ) -> list[Signal]:
        signals: list[Signal] = []
        seen: set[str] = set()
        for match in self.CONTACT_PATTERN.finditer(self._fold(text)):
            value = match.group(1)
            if value in seen:
                continue
            seen.add(value)
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.CONTACT_POINT_HIT,
                    signal_source="rule:contact_points",
                    risk_level=RiskLevel.HIGH,
                    risk_score=85,
                    summary=f"疑似联系方式或导流点：{value}",
                    payload_json={
                        "contact_point": value,
                        "row_index": row_index,
                        "source_ref": self._source_ref(dataset_id, row_index, record, dataset_platform),
                        "record_excerpt": text[:240],
                    },
                )
            )
        return signals

    def _extract_template_similarity(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        groups = self._group_by_template(records)
        signals: list[Signal] = []
        for template_key, row_indexes in groups.items():
            if len(row_indexes) < 2:
                continue
            source_refs = [
                self._source_ref(dataset_id, row_index, records[row_index], dataset_platform)
                for row_index in row_indexes
            ]
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.TEMPLATE_SIMILARITY_HIT,
                    signal_source=f"platform:{dataset_platform}:template_similarity",
                    risk_level=RiskLevel.HIGH,
                    risk_score=82,
                    summary=f"疑似模板复用：{len(row_indexes)} 条内容高度相似",
                    payload_json={
                        "template_key": template_key,
                        "row_indexes": row_indexes,
                        "source_refs": source_refs,
                        "source_ref": source_refs[0],
                    },
                )
            )
        return signals

    def _extract_abnormal_activity(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        signals: list[Signal] = []
        synchronized: dict[str, list[int]] = {}
        for row_index, record in enumerate(records):
            time_key = self._time_bucket(record)
            text_key = self._template_key(record)
            if time_key and text_key:
                synchronized.setdefault(f"{time_key}:{text_key}", []).append(row_index)

            engagement = self._number(record, "share_count") + self._number(record, "comment_count")
            likes = self._number(record, "liked_count") or self._number(record, "like_count")
            if engagement >= 500 and likes <= 5:
                source_ref = self._source_ref(dataset_id, row_index, record, dataset_platform)
                signals.append(
                    Signal(
                        dataset_id=dataset_id,
                        signal_type=SignalType.ABNORMAL_ACTIVITY_HIT,
                        signal_source=f"platform:{dataset_platform}:abnormal_activity",
                        risk_level=RiskLevel.MEDIUM,
                        risk_score=65,
                        summary="疑似异常互动：评论/转发高但点赞极低",
                        payload_json={
                            "row_index": row_index,
                            "engagement": engagement,
                            "likes": likes,
                            "source_ref": source_ref,
                        },
                    )
                )

        for key, row_indexes in synchronized.items():
            if len(row_indexes) < 2:
                continue
            source_refs = [
                self._source_ref(dataset_id, row_index, records[row_index], dataset_platform)
                for row_index in row_indexes
            ]
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.ABNORMAL_ACTIVITY_HIT,
                    signal_source=f"platform:{dataset_platform}:synchronized_activity",
                    risk_level=RiskLevel.HIGH,
                    risk_score=78,
                    summary=f"疑似同步发布或传播：{len(row_indexes)} 条记录同时间段话术接近",
                    payload_json={
                        "activity_key": key,
                        "row_indexes": row_indexes,
                        "source_refs": source_refs,
                        "source_ref": source_refs[0],
                    },
                )
            )
        return signals

    def _extract_seller_template_reuse(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        if dataset_platform != "xianyu":
            return []
        groups: dict[str, list[int]] = {}
        for row_index, record in enumerate(records):
            seller = str(record.get("seller_id") or record.get("user_id") or record.get("seller_name") or "").strip()
            template_key = self._template_key(record)
            if seller and template_key:
                groups.setdefault(f"{seller}:{template_key}", []).append(row_index)

        signals: list[Signal] = []
        for key, row_indexes in groups.items():
            if len(row_indexes) < 2:
                continue
            source_refs = [
                self._source_ref(dataset_id, row_index, records[row_index], dataset_platform)
                for row_index in row_indexes
            ]
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.SELLER_PRODUCT_CLUSTER_HIT,
                    signal_source="platform:xianyu:seller_template_reuse",
                    risk_level=RiskLevel.HIGH,
                    risk_score=84,
                    summary=f"闲鱼卖家疑似复用商品模板：{len(row_indexes)} 条商品",
                    payload_json={
                        "seller_template_key": key,
                        "row_indexes": row_indexes,
                        "source_refs": source_refs,
                        "source_ref": source_refs[0],
                    },
                )
            )
        return signals

    def _extract_abnormal_price_band(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        if dataset_platform != "xianyu":
            return []
        signals: list[Signal] = []
        for row_index, record in enumerate(records):
            price = self._number(record, "price") or self._number(record, "current_price")
            original_price = self._number(record, "original_price") or self._number(record, "market_price")
            if price <= 0:
                continue
            reason = ""
            risk_level = RiskLevel.MEDIUM
            risk_score = 62
            if price <= 5:
                reason = "价格低于 5，疑似异常低价引流"
                risk_level = RiskLevel.HIGH
                risk_score = 78
            elif original_price > 0 and price / original_price <= 0.12:
                reason = "现价低于原价 12%，疑似异常价格带"
                risk_level = RiskLevel.HIGH
                risk_score = 75
            if not reason:
                continue
            source_ref = self._source_ref(dataset_id, row_index, record, dataset_platform)
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.SELLER_PRODUCT_CLUSTER_HIT,
                    signal_source="platform:xianyu:abnormal_price_band",
                    risk_level=risk_level,
                    risk_score=risk_score,
                    summary=f"闲鱼商品异常价格：{reason}",
                    payload_json={
                        "price": price,
                        "original_price": original_price,
                        "row_index": row_index,
                        "source_ref": source_ref,
                    },
                )
            )
        return signals

    def _extract_xhs_comment_lead_diversion(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        if dataset_platform != "xhs":
            return []
        signals: list[Signal] = []
        for row_index, record in enumerate(records):
            text = self._record_text(record)
            is_comment = bool(record.get("comment_id") or record.get("comment_text") or record.get("parent_comment_id"))
            if not is_comment:
                continue
            lead_terms = [term for term in self.LEAD_DIVERSION_TERMS if term in text]
            contact_hits = [match.group(1) for match in self.CONTACT_PATTERN.finditer(text)]
            if not lead_terms and not contact_hits:
                continue
            source_ref = self._source_ref(dataset_id, row_index, record, dataset_platform)
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.CONTACT_POINT_HIT,
                    signal_source="platform:xhs:comment_lead_diversion",
                    risk_level=RiskLevel.HIGH,
                    risk_score=88 if contact_hits else 76,
                    summary="小红书评论疑似导流引导",
                    payload_json={
                        "lead_terms": lead_terms,
                        "contact_points": contact_hits,
                        "row_index": row_index,
                        "source_ref": source_ref,
                        "record_excerpt": text[:240],
                    },
                )
            )
        return signals

    def _extract_dy_script_diversion(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        if dataset_platform != "dy":
            return []
        signals: list[Signal] = []
        for row_index, record in enumerate(records):
            script_text = " ".join(str(record.get(field, "")) for field in self.DY_SCRIPT_FIELDS if record.get(field))
            if not script_text:
                continue
            lead_terms = [term for term in self.LEAD_DIVERSION_TERMS if term in script_text]
            contact_hits = [match.group(1) for match in self.CONTACT_PATTERN.finditer(script_text)]
            if not lead_terms and not contact_hits:
                continue
            source_ref = self._source_ref(dataset_id, row_index, record, dataset_platform)
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.RISK_TERM_HIT,
                    signal_source="platform:dy:script_diversion",
                    risk_level=RiskLevel.HIGH if contact_hits else RiskLevel.MEDIUM,
                    risk_score=82 if contact_hits else 68,
                    summary="抖音标题/字幕/口播疑似导流话术",
                    payload_json={
                        "lead_terms": lead_terms,
                        "contact_points": contact_hits,
                        "row_index": row_index,
                        "source_ref": source_ref,
                        "record_excerpt": script_text[:240],
                    },
                )
            )
        return signals

    def _extract_wb_topic_propagation(
        self,
        dataset_id: str,
        records: list[dict[str, Any]],
        dataset_platform: str,
    ) -> list[Signal]:
        if dataset_platform != "wb":
            return []
        groups: dict[str, list[int]] = {}
        for row_index, record in enumerate(records):
            topic = self._topic_key(record)
            template = self._template_key(record)
            time_key = self._time_bucket(record)
            if topic and template:
                groups.setdefault(f"{topic}:{time_key}:{template}", []).append(row_index)

        signals: list[Signal] = []
        for key, row_indexes in groups.items():
            if len(row_indexes) < 2:
                continue
            user_ids = {
                str(records[row_index].get("user_id") or records[row_index].get("uid") or "")
                for row_index in row_indexes
            }
            source_refs = [
                self._source_ref(dataset_id, row_index, records[row_index], dataset_platform)
                for row_index in row_indexes
            ]
            signals.append(
                Signal(
                    dataset_id=dataset_id,
                    signal_type=SignalType.ABNORMAL_ACTIVITY_HIT,
                    signal_source="platform:wb:topic_propagation",
                    risk_level=RiskLevel.HIGH if len(user_ids) > 1 else RiskLevel.MEDIUM,
                    risk_score=80 if len(user_ids) > 1 else 66,
                    summary=f"微博话题疑似同话术扩散：{len(row_indexes)} 条记录",
                    payload_json={
                        "propagation_key": key,
                        "row_indexes": row_indexes,
                        "user_ids": sorted(user_id for user_id in user_ids if user_id),
                        "source_refs": source_refs,
                        "source_ref": source_refs[0],
                    },
                )
            )
        return signals

    def _record_text(self, record: dict[str, Any]) -> str:
        return " ".join(str(value) for value in record.values() if value is not None)

    def _apply_aliases(self, text: str) -> str:
        """Rewrite known homophone/look-alike spellings to their canonical form."""
        for canonical, variants in self._VARIANT_ALIASES.items():
            for variant in variants:
                if variant in text:
                    text = text.replace(variant, canonical)
        return text

    def _fold(self, raw: str) -> str:
        """NFKC-fold, strip zero-width/combining marks, lowercase, de-alias.

        Neutralises full-width evasion (ｖｘ→vx, ＱＱ→qq), invisible separators
        and common homophones (薇信→微信) while preserving id structure
        (``_``/``-``), so it is safe for contact-point extraction where the
        captured value matters.
        """
        if not raw:
            return ""
        folded = unicodedata.normalize("NFKC", raw)
        folded = self._ZERO_WIDTH.sub("", folded)
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        return self._apply_aliases(folded.lower())

    def _collapse(self, raw: str) -> str:
        """Fold, drop every non-CJK / non-alphanumeric character, then de-alias.

        Defeats spacing, punctuation, symbol and emoji insertion between
        characters (``微❤信``, ``加 我``, ``v-x`` → ``微信``/``加我``/``vx``) and
        catches separator-split homophones (``薇 信`` → ``微信``), so keyword and
        co-occurrence matching survives obfuscation.
        """
        return self._apply_aliases(self._NON_TOKEN.sub("", self._fold(raw)))

    def _source_ref(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        dataset_platform: str | None = None,
    ) -> dict[str, Any]:
        return {
            "dataset_id": dataset_id,
            "row_index": row_index,
            "source_platform": record.get("source_platform") or record.get("platform") or dataset_platform,
            "source_entity_id": (
                record.get("source_entity_id")
                or record.get("comment_id")
                or record.get("note_id")
                or record.get("aweme_id")
                or record.get("weibo_id")
                or record.get("mblogid")
                or record.get("content_id")
                or record.get("product_id")
                or record.get("seller_id")
                or record.get("id")
            ),
            "raw_ref": record.get("raw_ref") or record.get("url") or record.get("source_url"),
        }

    def _topic_key(self, record: dict[str, Any]) -> str:
        raw = record.get("topic") or record.get("hashtag") or record.get("keyword") or record.get("source_keyword") or ""
        if isinstance(raw, list):
            return ",".join(str(item).strip() for item in raw if str(item).strip())
        text = str(raw).strip()
        if text:
            return text
        content = self._record_text(record)
        topics = re.findall(r"#([^#]{2,40})#", content)
        return ",".join(sorted(set(topic.strip() for topic in topics if topic.strip())))

    def _group_by_template(self, records: list[dict[str, Any]]) -> dict[str, list[int]]:
        groups: dict[str, list[int]] = {}
        for row_index, record in enumerate(records):
            key = self._template_key(record)
            if key:
                groups.setdefault(key, []).append(row_index)
        return groups

    def _template_key(self, record: dict[str, Any]) -> str:
        text_parts = [str(record.get(field, "")) for field in self.TEXT_FIELDS if record.get(field)]
        text = " ".join(text_parts) or self._record_text(record)
        normalized = re.sub(r"\s+", "", text.lower())
        normalized = re.sub(r"[0-9a-zA-Z_\-]{5,}", "<id>", normalized)
        normalized = re.sub(r"\d+(?:\.\d+)?", "<num>", normalized)
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized)
        if len(normalized) < 12:
            return ""
        return normalized[:80]

    def _time_bucket(self, record: dict[str, Any]) -> str:
        raw = (
            record.get("publish_time")
            or record.get("created_time")
            or record.get("create_time")
            or record.get("time")
            or ""
        )
        text = str(raw).strip()
        if len(text) >= 16:
            return text[:16]
        return text

    def _number(self, record: dict[str, Any], key: str) -> float:
        value = record.get(key)
        if value is None:
            return 0
        text = str(value).strip().replace(",", "")
        if text.endswith("万"):
            text = text[:-1]
            multiplier = 10000
        else:
            multiplier = 1
        try:
            return float(text) * multiplier
        except ValueError:
            return 0

    def _risk_score(self, risk_level: RiskLevel) -> float:
        return {
            RiskLevel.LOW: 30,
            RiskLevel.MEDIUM: 55,
            RiskLevel.HIGH: 80,
            RiskLevel.CRITICAL: 95,
        }[risk_level]
