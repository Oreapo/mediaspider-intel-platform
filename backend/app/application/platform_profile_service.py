from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.schemas.platform import PlatformProfileCreateRequest, PlatformProfileUpdateRequest
from ..domain.models.platform import AuthType, PlatformKey, PlatformProfile
from ..domain.repositories.platform_profile_repository import PlatformProfileRepository


class PlatformProfileService:
    def __init__(self, repository: PlatformProfileRepository):
        self.repository = repository

    def list_profiles(self, platform: PlatformKey | None = None) -> list[PlatformProfile]:
        return self.repository.list_profiles(platform)

    def get_profile(self, profile_id: str) -> PlatformProfile | None:
        return self.repository.get_profile(profile_id)

    def create_profile(self, payload: PlatformProfileCreateRequest) -> PlatformProfile:
        profile = PlatformProfile(**payload.model_dump())
        return self.repository.save_profile(profile)

    def update_profile(self, profile_id: str, payload: PlatformProfileUpdateRequest) -> PlatformProfile:
        existing = self.repository.get_profile(profile_id)
        if existing is None:
            raise ValueError(f"Platform profile {profile_id} not found")
        updated = existing.model_copy(
            update={
                **payload.model_dump(exclude_unset=True),
                "updated_at": datetime.utcnow(),
            }
        )
        return self.repository.save_profile(updated)

    def delete_profile(self, profile_id: str) -> bool:
        return self.repository.delete_profile(profile_id)

    def resolve_runtime_auth(self, profile_id: str) -> dict[str, Any]:
        profile = self.repository.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Platform profile {profile_id} not found")
        payload: dict[str, Any] = {"auth_type": profile.auth_type.value, "auth_profile_id": profile.id}
        if profile.auth_type == AuthType.COOKIE:
            payload["cookies"] = profile.credentials_ref
        elif profile.auth_type == AuthType.STATE_FILE:
            payload["state_file"] = profile.credentials_ref
        elif profile.credentials_ref:
            payload["credentials_ref"] = profile.credentials_ref
        payload.update({key: value for key, value in profile.settings_json.items() if value is not None})
        return payload

    def diagnose_profile(self, profile_id: str) -> dict[str, object]:
        profile = self.repository.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Platform profile {profile_id} not found")
        errors: list[str] = []
        warnings: list[str] = []
        if profile.auth_type in {AuthType.COOKIE, AuthType.STATE_FILE} and not profile.credentials_ref.strip():
            errors.append("credentials_ref is required for cookie/state_file authentication")
        if profile.auth_type == AuthType.STATE_FILE and profile.credentials_ref:
            state_path = Path(profile.credentials_ref).expanduser()
            if not state_path.exists():
                warnings.append("state_file does not exist on this machine")
        if profile.auth_type in {AuthType.QRCODE, AuthType.PHONE}:
            warnings.append("interactive login is not yet automated; use cookie or state_file for scheduled runs")
        return {
            "ready": not errors,
            "errors": errors,
            "warnings": warnings,
            "profile": self.sanitize_profile(profile),
            "runtime_keys": sorted(self.resolve_runtime_auth(profile.id).keys()) if not errors else [],
        }

    def sanitize_profile(self, profile: PlatformProfile) -> dict[str, Any]:
        data = profile.model_dump(mode="json")
        if data.get("credentials_ref"):
            data["credentials_ref"] = self._redact(str(data["credentials_ref"]))
        return data

    def _redact(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"
