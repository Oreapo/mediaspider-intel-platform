from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..dependencies import ANALYST_ROLES, READ_ROLES, get_audit_service, get_evidence_service, require_roles, require_user
from ..schemas.evidence import EvidencePacketCreateRequest
from ...application.audit_service import AuditService
from ...application.auth_service import AuthUser
from ...application.evidence_service import EvidenceService


router = APIRouter(prefix="/evidence", tags=["evidence"], dependencies=[Depends(require_roles(*READ_ROLES))])


@router.get("")
def list_evidence_packets(
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: EvidenceService = Depends(get_evidence_service),
):
    packets, total = service.list_packets_page(limit=limit, offset=offset)
    return {"packets": [packet.model_dump(mode="json") for packet in packets], "total": total}


@router.post("/packets", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def generate_evidence_packet(
    payload: EvidencePacketCreateRequest,
    service: EvidenceService = Depends(get_evidence_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    try:
        packet = service.generate_packet(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_service.record(
        action="evidence_packet.generate",
        actor=actor,
        target_type="evidence_packet",
        target_id=packet.id,
        summary=f"生成证据包：{packet.packet_name}",
        metadata_json={"case_id": packet.case_id, "storage_uri": packet.storage_uri},
    )
    return {"message": "Evidence packet generated", "packet": packet.model_dump(mode="json")}


@router.get("/{packet_id}")
def get_evidence_packet(packet_id: str, service: EvidenceService = Depends(get_evidence_service)):
    packet = service.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Evidence packet not found")
    return {"packet": packet.model_dump(mode="json")}


@router.get("/{packet_id}/download")
def download_evidence_packet(
    packet_id: str,
    service: EvidenceService = Depends(get_evidence_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_user),
):
    packet = service.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Evidence packet not found")
    path = service.resolve_packet_path(packet.storage_uri)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence packet artifact not found")
    audit_service.record(
        action="evidence_packet.download",
        actor=actor,
        target_type="evidence_packet",
        target_id=packet.id,
        summary=f"下载证据包：{packet.packet_name}",
        metadata_json={"case_id": packet.case_id, "storage_uri": packet.storage_uri},
    )
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"{packet.packet_name}.json",
    )


@router.delete("/{packet_id}", dependencies=[Depends(require_roles(*ANALYST_ROLES))])
def delete_evidence_packet(
    packet_id: str,
    delete_storage: bool = Query(False),
    service: EvidenceService = Depends(get_evidence_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: AuthUser = Depends(require_roles(*ANALYST_ROLES)),
):
    packet = service.get_packet(packet_id)
    deleted = service.delete_packet(packet_id, delete_storage=delete_storage)
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence packet not found")
    audit_service.record(
        action="evidence_packet.delete",
        actor=actor,
        target_type="evidence_packet",
        target_id=packet_id,
        summary=f"删除证据包：{packet.packet_name if packet else packet_id}",
        metadata_json={"delete_storage": delete_storage, "case_id": packet.case_id if packet else ""},
    )
    return {"message": "Evidence packet deleted"}
