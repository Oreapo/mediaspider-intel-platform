from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.entity import EntityRelation, RiskEntity, RiskEntityStatus, RiskEntityType
from ..models.platform import PlatformKey


class EntityRepository(ABC):
    @abstractmethod
    def list_entities(
        self,
        *,
        platform: PlatformKey | None = None,
        entity_type: RiskEntityType | None = None,
        status: RiskEntityStatus | None = None,
        min_risk_score: float | None = None,
        query: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[RiskEntity]:
        raise NotImplementedError

    @abstractmethod
    def count_entities(
        self,
        *,
        platform: PlatformKey | None = None,
        entity_type: RiskEntityType | None = None,
        status: RiskEntityStatus | None = None,
        min_risk_score: float | None = None,
        query: str = "",
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_entity(self, entity_id: str) -> RiskEntity | None:
        raise NotImplementedError

    @abstractmethod
    def save_entity(self, entity: RiskEntity) -> RiskEntity:
        raise NotImplementedError

    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_relations(self) -> list[EntityRelation]:
        raise NotImplementedError

    @abstractmethod
    def get_relation(self, relation_id: str) -> EntityRelation | None:
        raise NotImplementedError

    @abstractmethod
    def save_relation(self, relation: EntityRelation) -> EntityRelation:
        raise NotImplementedError

    @abstractmethod
    def delete_relation(self, relation_id: str) -> bool:
        raise NotImplementedError
