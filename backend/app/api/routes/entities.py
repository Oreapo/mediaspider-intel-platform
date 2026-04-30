from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_entity_service
from ..schemas.entity import (
    EntityFromSignalRequest,
    EntityMergeRequest,
    EntityRelationCreateRequest,
    EntityStatusUpdateRequest,
    RiskEntityCreateRequest,
)
from ...application.entity_service import EntityService


router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("")
def list_entities(service: EntityService = Depends(get_entity_service)):
    return {"entities": [entity.model_dump(mode="json") for entity in service.list_entities()]}


@router.post("")
def create_entity(
    payload: RiskEntityCreateRequest,
    service: EntityService = Depends(get_entity_service),
):
    entity = service.create_entity(payload)
    return {"message": "Entity created", "entity": entity.model_dump(mode="json")}


@router.post("/from-signal")
def create_entity_from_signal(
    payload: EntityFromSignalRequest,
    service: EntityService = Depends(get_entity_service),
):
    try:
        entity = service.create_from_signal(
            signal_id=payload.signal_id,
            entity_type=payload.entity_type,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"message": "Entity created from signal", "entity": entity.model_dump(mode="json")}


@router.get("/relations")
def list_relations(service: EntityService = Depends(get_entity_service)):
    return {"relations": [relation.model_dump(mode="json") for relation in service.list_relations()]}


@router.post("/relations")
def create_relation(
    payload: EntityRelationCreateRequest,
    service: EntityService = Depends(get_entity_service),
):
    try:
        relation = service.create_relation(**payload.model_dump())
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"message": "Relation created", "relation": relation.model_dump(mode="json")}


@router.delete("/relations/{relation_id}")
def delete_relation(relation_id: str, service: EntityService = Depends(get_entity_service)):
    deleted = service.delete_relation(relation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relation not found")
    return {"message": "Relation deleted"}


@router.post("/merge")
def merge_entities(
    payload: EntityMergeRequest,
    service: EntityService = Depends(get_entity_service),
):
    try:
        result = service.merge_entities(**payload.model_dump())
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {
        "message": "Entities merged",
        "source_entity": result["source_entity"].model_dump(mode="json"),
        "target_entity": result["target_entity"].model_dump(mode="json"),
        "relation": result["relation"].model_dump(mode="json"),
    }


@router.get("/{entity_id}")
def get_entity_detail(entity_id: str, service: EntityService = Depends(get_entity_service)):
    detail = service.get_entity_detail(entity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return detail


@router.patch("/{entity_id}/status")
def update_entity_status(
    entity_id: str,
    payload: EntityStatusUpdateRequest,
    service: EntityService = Depends(get_entity_service),
):
    try:
        entity = service.update_status(entity_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Entity status updated", "entity": entity.model_dump(mode="json")}


@router.delete("/{entity_id}")
def delete_entity(entity_id: str, service: EntityService = Depends(get_entity_service)):
    deleted = service.delete_entity(entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"message": "Entity deleted"}
