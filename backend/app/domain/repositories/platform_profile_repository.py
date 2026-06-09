from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.platform import PlatformKey, PlatformProfile


class PlatformProfileRepository(ABC):
    @abstractmethod
    def list_profiles(self, platform: PlatformKey | None = None) -> list[PlatformProfile]:
        raise NotImplementedError

    @abstractmethod
    def get_profile(self, profile_id: str) -> PlatformProfile | None:
        raise NotImplementedError

    @abstractmethod
    def save_profile(self, profile: PlatformProfile) -> PlatformProfile:
        raise NotImplementedError

    @abstractmethod
    def delete_profile(self, profile_id: str) -> bool:
        raise NotImplementedError
