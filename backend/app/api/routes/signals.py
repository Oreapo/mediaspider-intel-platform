from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_signal_service
from ..schemas.signal import SignalCreateRequest, SignalExtractionRequest, SignalStatusUpdateRequest
from ...application.signal_service import SignalService


router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
def list_signals(service: SignalService = Depends(get_signal_service)):
    return {"signals": [signal.model_dump(mode="json") for signal in service.list_signals()]}


@router.post("/extract")
def extract_signals(
    payload: SignalExtractionRequest,
    service: SignalService = Depends(get_signal_service),
):
    try:
        signals = service.extract_from_dataset(
            dataset_id=payload.dataset_id,
            extractors=payload.extractors,
            limit=payload.limit,
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return {
        "message": "Signals extracted",
        "signals": [signal.model_dump(mode="json") for signal in signals],
    }


@router.get("/{signal_id}")
def get_signal(signal_id: str, service: SignalService = Depends(get_signal_service)):
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"signal": signal.model_dump(mode="json")}


@router.post("")
def create_signal(
    payload: SignalCreateRequest,
    service: SignalService = Depends(get_signal_service),
):
    try:
        signal = service.create_signal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Signal created", "signal": signal.model_dump(mode="json")}


@router.patch("/{signal_id}/status")
def update_signal_status(
    signal_id: str,
    payload: SignalStatusUpdateRequest,
    service: SignalService = Depends(get_signal_service),
):
    try:
        signal = service.update_status(signal_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "Signal status updated", "signal": signal.model_dump(mode="json")}


@router.delete("/{signal_id}")
def delete_signal(signal_id: str, service: SignalService = Depends(get_signal_service)):
    deleted = service.delete_signal(signal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"message": "Signal deleted"}

