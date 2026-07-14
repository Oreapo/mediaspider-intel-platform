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
# Roles allowed to view unmasked personal data on demand.
_REVEAL_ROLES = {"admin"}
# Column-name fragments that mark a preview column as holding a contact value.
_CONTACT_COLUMN_HINTS = (
    "contact",
    "phone",
    "mobile",
    "tel",
    "wechat",
    "weixin",
    "vx",
    "qq",
    "email",
)


def masking_enabled() -> bool:
    return os.getenv("MEDIASPIDER_PII_MASKING", "false").strip().lower() in _TRUTHY


def can_reveal_pii(role: str) -> bool:
    """Whether a role may request unmasked personal data."""
    return role in _REVEAL_ROLES


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


def _is_contact_column(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _CONTACT_COLUMN_HINTS)


def mask_preview(preview: dict[str, Any]) -> dict[str, Any]:
    """Mask contact columns and phone numbers in a dataset preview table."""
    columns = preview.get("columns")
    rows = preview.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return preview

    contact_columns = {index for index, column in enumerate(columns) if _is_contact_column(str(column))}
    masked_rows: list[Any] = []
    for row in rows:
        if not isinstance(row, list):
            masked_rows.append(row)
            continue
        masked_row = []
        for index, cell in enumerate(row):
            if isinstance(cell, str) and cell.strip():
                if index in contact_columns:
                    masked_row.append(mask_value(cell))
                else:
                    masked_row.append(_mask_text(cell, {}))
            else:
                masked_row.append(cell)
        masked_rows.append(masked_row)

    result = dict(preview)
    result["rows"] = masked_rows
    return result


def mask_cluster(cluster: dict[str, Any]) -> dict[str, Any]:
    """Mask contact points (and any contact echoed in the label) of a gang cluster."""
    result = dict(cluster)
    contact = result.get("contact_point")
    if isinstance(contact, str) and contact.strip():
        result["contact_point"] = mask_value(contact)
    contacts = result.get("contact_points")
    if isinstance(contacts, list):
        result["contact_points"] = [
            mask_value(item) if isinstance(item, str) and item.strip() else item for item in contacts
        ]
    label = result.get("label")
    if isinstance(label, str) and isinstance(contact, str) and contact and contact in label:
        result["label"] = label.replace(contact, mask_value(contact))
    return result


def mask_clusters(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [mask_cluster(cluster) for cluster in clusters]
