"""Display-time masking of personal data in signal responses.

Masking is applied only when serialising API responses; the underlying stored
data is never modified, so authorised evidence workflows keep the full value.
Enable with MEDIASPIDER_PII_MASKING=true.
"""

from __future__ import annotations

import copy
import os
import re
from typing import Any

# Mainland China mobile numbers — masked to keep the prefix and last four.
_PHONE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_TRUTHY = {"1", "true", "yes", "on"}


def masking_enabled() -> bool:
    return os.getenv("MEDIASPIDER_PII_MASKING", "false").strip().lower() in _TRUTHY


def mask_value(value: str) -> str:
    """Mask a contact id/number, keeping a little context at each end."""
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    if len(text) <= 5:
        return text[0] + "*" * (len(text) - 1)
    return text[:2] + "*" * (len(text) - 4) + text[-2:]


def _mask_text(text: str, replacements: dict[str, str]) -> str:
    for raw, masked in replacements.items():
        if raw:
            text = text.replace(raw, masked)
    return _PHONE.sub(lambda match: f"{match.group(1)}****{match.group(2)}", text)


def mask_signal(signal: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a serialised signal with contact data masked."""
    payload = signal.get("payload_json")
    replacements: dict[str, str] = {}
    if isinstance(payload, dict):
        contact = payload.get("contact_point")
        if isinstance(contact, str) and contact.strip():
            replacements[contact] = mask_value(contact)
        for contact in payload.get("contact_points") or []:
            if isinstance(contact, str) and contact.strip():
                replacements[contact] = mask_value(contact)

    masked = copy.deepcopy(signal)
    new_payload = masked.get("payload_json")
    if isinstance(new_payload, dict):
        if isinstance(new_payload.get("contact_point"), str):
            new_payload["contact_point"] = replacements.get(
                new_payload["contact_point"], mask_value(new_payload["contact_point"])
            )
        if isinstance(new_payload.get("contact_points"), list):
            new_payload["contact_points"] = [
                replacements.get(contact, mask_value(contact)) if isinstance(contact, str) else contact
                for contact in new_payload["contact_points"]
            ]
        if isinstance(new_payload.get("record_excerpt"), str):
            new_payload["record_excerpt"] = _mask_text(new_payload["record_excerpt"], replacements)
    if isinstance(masked.get("summary"), str):
        masked["summary"] = _mask_text(masked["summary"], replacements)
    return masked


def mask_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [mask_signal(signal) for signal in signals]
