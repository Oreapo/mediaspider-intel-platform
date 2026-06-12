from __future__ import annotations

import re
from datetime import datetime
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
        signals, _ = self.list_signals_page(
            dataset_id=dataset_id,
            status=status,
            risk_level=risk_level,
            signal_type=signal_type,
            query=query,
            limit=limit,
            offset=offset,
        )
        return signals

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

    def extract_from_dataset(
        self,
        *,
        dataset_id: str,
        extractors: list[str] | None = None,
        limit: int = 100,
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

        for signal in created:
            self.repository.save_signal(signal)
        return created

    def _extract_risk_terms(
        self,
        dataset_id: str,
        row_index: int,
        record: dict[str, Any],
        text: str,
        dataset_platform: str,
    ) -> list[Signal]:
        signals: list[Signal] = []
        for term, risk_level in self.RISK_TERMS.items():
            if term not in text:
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
                        "row_index": row_index,
                        "source_ref": self._source_ref(dataset_id, row_index, record, dataset_platform),
                        "record_excerpt": text[:240],
                    },
                )
            )
        return signals

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
        for match in self.CONTACT_PATTERN.finditer(text):
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
