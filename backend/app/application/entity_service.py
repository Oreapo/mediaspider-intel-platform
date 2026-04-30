from __future__ import annotations

from datetime import datetime
from typing import Any

from ..api.schemas.entity import RiskEntityCreateRequest
from ..domain.models.entity import EntityRelation, RiskEntity, RiskEntityStatus, RiskEntityType
from ..domain.models.signal import SignalStatus, SignalType
from ..domain.repositories.entity_repository import EntityRepository
from .dataset_service import DatasetService
from .signal_service import SignalService


class EntityService:
    def __init__(
        self,
        repository: EntityRepository,
        signal_service: SignalService,
        dataset_service: DatasetService,
    ):
        self.repository = repository
        self.signal_service = signal_service
        self.dataset_service = dataset_service

    def list_entities(self) -> list[RiskEntity]:
        return self.repository.list_entities()

    def get_entity(self, entity_id: str) -> RiskEntity | None:
        return self.repository.get_entity(entity_id)

    def get_entity_detail(self, entity_id: str) -> dict[str, Any] | None:
        entity = self.repository.get_entity(entity_id)
        if entity is None:
            return None
        linked_signal_ids = set(entity.profile_json.get("linked_signal_ids") or [])
        related_signals = [
            signal.model_dump(mode="json")
            for signal in self.signal_service.list_signals()
            if signal.id in linked_signal_ids
        ]
        related_dataset_ids = sorted(
            {
                signal["dataset_id"]
                for signal in related_signals
                if signal.get("dataset_id")
            }
        )
        related_datasets = [
            dataset.model_dump(mode="json")
            for dataset_id in related_dataset_ids
            if (dataset := self.dataset_service.get_dataset(dataset_id)) is not None
        ]
        relations = [
            relation.model_dump(mode="json")
            for relation in self.repository.list_relations()
            if relation.source_entity_id == entity_id or relation.target_entity_id == entity_id
        ]
        return {
            "entity": entity.model_dump(mode="json"),
            "signals": related_signals,
            "datasets": related_datasets,
            "relations": relations,
            "cases": [],
        }

    def create_entity(self, payload: RiskEntityCreateRequest) -> RiskEntity:
        entity = RiskEntity(**payload.model_dump())
        duplicate = self._find_duplicate(entity)
        if duplicate is not None:
            return self._merge_entity_data(duplicate, entity)
        return self.repository.save_entity(entity)

    def create_from_signal(
        self,
        *,
        signal_id: str,
        entity_type: RiskEntityType | None = None,
        display_name: str | None = None,
    ) -> RiskEntity:
        signal = self.signal_service.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"Signal {signal_id} not found")
        if signal.status != SignalStatus.CONFIRMED:
            raise ValueError("Only confirmed signals can create entities")
        dataset = self.dataset_service.get_dataset(signal.dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {signal.dataset_id} not found")

        source_ref = self._source_ref_from_signal(signal_id, signal.payload_json)
        inferred_type = entity_type or self._infer_entity_type(signal.signal_type, source_ref)
        inferred_name = display_name or self._display_name(signal.summary, source_ref, inferred_type)
        aliases = self._aliases(inferred_name, source_ref)
        entity = RiskEntity(
            entity_type=inferred_type,
            display_name=inferred_name,
            platform=dataset.source_platform,
            source_ref=source_ref,
            risk_score=signal.risk_score,
            profile_json={
                "aliases": aliases,
                "linked_signal_ids": [signal.id],
                "source_refs": [source_ref],
            },
        )
        duplicate = self._find_duplicate(entity)
        if duplicate is not None:
            return self._merge_entity_data(duplicate, entity)
        return self.repository.save_entity(entity)

    def update_status(self, entity_id: str, status: RiskEntityStatus) -> RiskEntity:
        entity = self.repository.get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Entity {entity_id} not found")
        updated = entity.model_copy(update={"status": status, "updated_at": datetime.utcnow()})
        return self.repository.save_entity(updated)

    def delete_entity(self, entity_id: str) -> bool:
        return self.repository.delete_entity(entity_id)

    def list_relations(self) -> list[EntityRelation]:
        return self.repository.list_relations()

    def create_relation(
        self,
        *,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        confidence: float,
        evidence_ref_json: dict[str, Any] | None = None,
    ) -> EntityRelation:
        if source_entity_id == target_entity_id:
            raise ValueError("Relation endpoints must be different entities")
        source = self.repository.get_entity(source_entity_id)
        target = self.repository.get_entity(target_entity_id)
        if source is None:
            raise ValueError(f"Entity {source_entity_id} not found")
        if target is None:
            raise ValueError(f"Entity {target_entity_id} not found")

        evidence = evidence_ref_json or {}
        duplicate = self._find_duplicate_relation(source_entity_id, target_entity_id, relation_type)
        if duplicate is not None:
            merged_evidence = self._merge_evidence(duplicate.evidence_ref_json, evidence)
            updated = duplicate.model_copy(
                update={
                    "confidence": max(duplicate.confidence, confidence),
                    "evidence_ref_json": merged_evidence,
                    "updated_at": datetime.utcnow(),
                }
            )
            return self.repository.save_relation(updated)

        relation = EntityRelation(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            confidence=confidence,
            evidence_ref_json=evidence,
        )
        return self.repository.save_relation(relation)

    def merge_entities(
        self,
        *,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        confidence: float,
        evidence_ref_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = self.repository.get_entity(source_entity_id)
        target = self.repository.get_entity(target_entity_id)
        if source is None:
            raise ValueError(f"Entity {source_entity_id} not found")
        if target is None:
            raise ValueError(f"Entity {target_entity_id} not found")
        if source.id == target.id:
            raise ValueError("Cannot merge an entity into itself")

        merged_target = self._merge_entity_data(target, source)
        merged_source = source.model_copy(
            update={
                "status": RiskEntityStatus.MERGED,
                "profile_json": {
                    **source.profile_json,
                    "merged_into_entity_id": target.id,
                },
                "updated_at": datetime.utcnow(),
            }
        )
        self.repository.save_entity(merged_source)
        relation = self.create_relation(
            source_entity_id=source.id,
            target_entity_id=target.id,
            relation_type=relation_type,
            confidence=confidence,
            evidence_ref_json=evidence_ref_json or {"merged_entity_id": source.id},
        )
        return {
            "source_entity": merged_source,
            "target_entity": merged_target,
            "relation": relation,
        }

    def delete_relation(self, relation_id: str) -> bool:
        return self.repository.delete_relation(relation_id)

    def _source_ref_from_signal(self, signal_id: str, payload_json: dict[str, Any]) -> dict[str, Any]:
        raw_source_ref = payload_json.get("source_ref")
        source_ref = dict(raw_source_ref) if isinstance(raw_source_ref, dict) else {}
        source_ref["signal_id"] = signal_id
        if "contact_point" in payload_json:
            source_ref["contact_point"] = payload_json["contact_point"]
        return source_ref

    def _infer_entity_type(self, signal_type: SignalType, source_ref: dict[str, Any]) -> RiskEntityType:
        if signal_type == SignalType.CONTACT_POINT_HIT or source_ref.get("contact_point"):
            return RiskEntityType.CONTACT_POINT
        if source_ref.get("seller_id"):
            return RiskEntityType.SELLER
        if source_ref.get("product_id"):
            return RiskEntityType.PRODUCT
        if source_ref.get("source_entity_id"):
            return RiskEntityType.CONTENT
        return RiskEntityType.UNKNOWN

    def _display_name(self, summary: str, source_ref: dict[str, Any], entity_type: RiskEntityType) -> str:
        if entity_type == RiskEntityType.CONTACT_POINT and source_ref.get("contact_point"):
            return str(source_ref["contact_point"])
        for key in ("display_name", "source_entity_id", "seller_id", "product_id", "raw_ref"):
            if source_ref.get(key):
                return str(source_ref[key])
        return summary[:80]

    def _aliases(self, display_name: str, source_ref: dict[str, Any]) -> list[str]:
        candidates = [
            display_name,
            source_ref.get("contact_point"),
            source_ref.get("source_entity_id"),
            source_ref.get("seller_id"),
            source_ref.get("product_id"),
            source_ref.get("raw_ref"),
        ]
        aliases: list[str] = []
        for value in candidates:
            if value is None:
                continue
            alias = str(value).strip().lower()
            if alias and alias not in aliases:
                aliases.append(alias)
        return aliases

    def _find_duplicate(self, entity: RiskEntity) -> RiskEntity | None:
        incoming_aliases = set(self._aliases(entity.display_name, entity.source_ref))
        incoming_aliases.update(str(alias).lower() for alias in entity.profile_json.get("aliases", []))
        for existing in self.repository.list_entities():
            if existing.status == RiskEntityStatus.MERGED:
                continue
            if existing.platform != entity.platform or existing.entity_type != entity.entity_type:
                continue
            existing_aliases = set(self._aliases(existing.display_name, existing.source_ref))
            existing_aliases.update(str(alias).lower() for alias in existing.profile_json.get("aliases", []))
            if incoming_aliases & existing_aliases:
                return existing
        return None

    def _merge_entity_data(self, existing: RiskEntity, incoming: RiskEntity) -> RiskEntity:
        profile = dict(existing.profile_json)
        profile["aliases"] = self._unique_list(
            list(profile.get("aliases") or []) + list(incoming.profile_json.get("aliases") or [])
        )
        profile["linked_signal_ids"] = self._unique_list(
            list(profile.get("linked_signal_ids") or []) + list(incoming.profile_json.get("linked_signal_ids") or [])
        )
        profile["source_refs"] = self._unique_refs(
            list(profile.get("source_refs") or []) + list(incoming.profile_json.get("source_refs") or [incoming.source_ref])
        )
        updated = existing.model_copy(
            update={
                "risk_score": max(existing.risk_score, incoming.risk_score),
                "profile_json": profile,
                "updated_at": datetime.utcnow(),
            }
        )
        return self.repository.save_entity(updated)

    def _find_duplicate_relation(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
    ) -> EntityRelation | None:
        endpoints = {source_entity_id, target_entity_id}
        for relation in self.repository.list_relations():
            if relation.relation_type != relation_type:
                continue
            if {relation.source_entity_id, relation.target_entity_id} == endpoints:
                return relation
        return None

    def _merge_evidence(self, existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing)
        for key, value in incoming.items():
            if key not in merged:
                merged[key] = value
            elif merged[key] != value:
                values = merged[key] if isinstance(merged[key], list) else [merged[key]]
                if value not in values:
                    values.append(value)
                merged[key] = values
        return merged

    def _unique_list(self, values: list[Any]) -> list[Any]:
        result: list[Any] = []
        for value in values:
            if value not in result:
                result.append(value)
        return result

    def _unique_refs(self, refs: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        fingerprints: set[str] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            fingerprint = repr(sorted(ref.items()))
            if fingerprint not in fingerprints:
                fingerprints.add(fingerprint)
                result.append(ref)
        return result
