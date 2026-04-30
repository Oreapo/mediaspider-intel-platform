from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.entity import EntityRelation, RiskEntity
from ...domain.repositories.entity_repository import EntityRepository


class JsonEntityRepository(EntityRepository):
    def __init__(self, entities_file: Path, relations_file: Path):
        self.entities_file = entities_file
        self.relations_file = relations_file

    def list_entities(self) -> list[RiskEntity]:
        return sorted(self._load_entities(), key=lambda entity: entity.updated_at, reverse=True)

    def get_entity(self, entity_id: str) -> RiskEntity | None:
        for entity in self._load_entities():
            if entity.id == entity_id:
                return entity
        return None

    def save_entity(self, entity: RiskEntity) -> RiskEntity:
        entities = self._load_entities()
        replaced = False
        for index, existing in enumerate(entities):
            if existing.id == entity.id:
                entities[index] = entity
                replaced = True
                break
        if not replaced:
            entities.append(entity)
        self._save_entities(entities)
        return entity

    def delete_entity(self, entity_id: str) -> bool:
        entities = self._load_entities()
        filtered = [entity for entity in entities if entity.id != entity_id]
        if len(filtered) == len(entities):
            return False
        self._save_entities(filtered)
        return True

    def list_relations(self) -> list[EntityRelation]:
        return sorted(self._load_relations(), key=lambda relation: relation.updated_at, reverse=True)

    def get_relation(self, relation_id: str) -> EntityRelation | None:
        for relation in self._load_relations():
            if relation.id == relation_id:
                return relation
        return None

    def save_relation(self, relation: EntityRelation) -> EntityRelation:
        relations = self._load_relations()
        replaced = False
        for index, existing in enumerate(relations):
            if existing.id == relation.id:
                relations[index] = relation
                replaced = True
                break
        if not replaced:
            relations.append(relation)
        self._save_relations(relations)
        return relation

    def delete_relation(self, relation_id: str) -> bool:
        relations = self._load_relations()
        filtered = [relation for relation in relations if relation.id != relation_id]
        if len(filtered) == len(relations):
            return False
        self._save_relations(filtered)
        return True

    def _load_entities(self) -> list[RiskEntity]:
        if not self.entities_file.exists():
            return []
        try:
            raw = json.loads(self.entities_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        entities: list[RiskEntity] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                entities.append(RiskEntity.model_validate(item))
            except Exception:
                continue
        return entities

    def _load_relations(self) -> list[EntityRelation]:
        if not self.relations_file.exists():
            return []
        try:
            raw = json.loads(self.relations_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        relations: list[EntityRelation] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                relations.append(EntityRelation.model_validate(item))
            except Exception:
                continue
        return relations

    def _save_entities(self, entities: list[RiskEntity]) -> None:
        self.entities_file.parent.mkdir(parents=True, exist_ok=True)
        self.entities_file.write_text(
            json.dumps([entity.model_dump(mode="json") for entity in entities], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_relations(self, relations: list[EntityRelation]) -> None:
        self.relations_file.parent.mkdir(parents=True, exist_ok=True)
        self.relations_file.write_text(
            json.dumps([relation.model_dump(mode="json") for relation in relations], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
