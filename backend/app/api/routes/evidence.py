from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..dependencies import get_evidence_service
from ..schemas.evidence import EvidencePacketCreateRequest
from ...application.evidence_service import EvidenceService


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("")
def list_evidence_packets(service: EvidenceService = Depends(get_evidence_service)):
    return {"packets": [packet.model_dump(mode="json") for packet in service.list_packets()]}


@router.post("/packets")
def generate_evidence_packet(
    payload: EvidencePacketCreateRequest,
    service: EvidenceService = Depends(get_evidence_service),
):
    try:
        packet = service.generate_packet(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Evidence packet generated", "packet": packet.model_dump(mode="json")}


@router.get("/{packet_id}")
def get_evidence_packet(packet_id: str, service: EvidenceService = Depends(get_evidence_service)):
    packet = service.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Evidence packet not found")
    return {"packet": packet.model_dump(mode="json")}


@router.get("/{packet_id}/download")
def download_evidence_packet(packet_id: str, service: EvidenceService = Depends(get_evidence_service)):
    packet = service.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Evidence packet not found")
    path = service.resolve_packet_path(packet.storage_uri)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence packet artifact not found")
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"{packet.packet_name}.json",
    )


@router.delete("/{packet_id}")
def delete_evidence_packet(
    packet_id: str,
    delete_storage: bool = Query(False),
    service: EvidenceService = Depends(get_evidence_service),
):
    deleted = service.delete_packet(packet_id, delete_storage=delete_storage)
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence packet not found")
    return {"message": "Evidence packet deleted"}
