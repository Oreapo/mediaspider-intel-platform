from __future__ import annotations

import json
from pathlib import Path

from ...domain.models.platform import PlatformKey, PlatformProfile
from ...domain.repositories.platform_profile_repository import PlatformProfileRepository


class JsonPlatformProfileRepository(PlatformProfileRepository):
    def __init__(self, storage_file: Path):
        self.storage_file = storage_file

    def list_profiles(self, platform: PlatformKey | None = None) -> list[PlatformProfile]:
        profiles = self._load_all()
        if platform is not None:
            profiles = [profile for profile in profiles if profile.platform == platform]
        return sorted(profiles, key=lambda profile: profile.updated_at, reverse=True)

    def get_profile(self, profile_id: str) -> PlatformProfile | None:
        for profile in self._load_all():
            if profile.id == profile_id:
                return profile
        return None

    def save_profile(self, profile: PlatformProfile) -> PlatformProfile:
        profiles = self._load_all()
        replaced = False
        for index, existing in enumerate(profiles):
            if existing.id == profile.id:
                profiles[index] = profile
                replaced = True
                break
        if not replaced:
            profiles.append(profile)
        self._save_all(profiles)
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        profiles = self._load_all()
        filtered = [profile for profile in profiles if profile.id != profile_id]
        if len(filtered) == len(profiles):
            return False
        self._save_all(filtered)
        return True

    def _load_all(self) -> list[PlatformProfile]:
        if not self.storage_file.exists():
            return []
        try:
            raw = json.loads(self.storage_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        profiles: list[PlatformProfile] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                profiles.append(PlatformProfile.model_validate(item))
            except Exception:
                continue
        return profiles

    def _save_all(self, profiles: list[PlatformProfile]) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.storage_file.write_text(
            json.dumps([profile.model_dump(mode="json") for profile in profiles], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
