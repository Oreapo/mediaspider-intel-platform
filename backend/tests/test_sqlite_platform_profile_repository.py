from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.models.platform import AuthType, PlatformKey, PlatformProfile
from app.infrastructure.persistence.sqlite_platform_profile_repository import SQLitePlatformProfileRepository


def test_sqlite_platform_profile_repository_crud(tmp_path):
    repository = SQLitePlatformProfileRepository(tmp_path / "storage.sqlite3")
    now = datetime.utcnow()
    first = PlatformProfile(
        id="pf_first",
        platform=PlatformKey.XHS,
        profile_name="First",
        auth_type=AuthType.COOKIE,
        credentials_ref="cookie-a",
        settings_json={"headless": True},
        created_at=now,
        updated_at=now,
    )
    second = PlatformProfile(
        id="pf_second",
        platform=PlatformKey.DY,
        profile_name="Second",
        auth_type=AuthType.STATE_FILE,
        credentials_ref="state.json",
        created_at=now + timedelta(minutes=1),
        updated_at=now + timedelta(minutes=1),
    )

    repository.save_profile(first)
    repository.save_profile(second)

    assert repository.get_profile("pf_first") == first
    assert [item.id for item in repository.list_profiles()] == ["pf_second", "pf_first"]
    assert [item.id for item in repository.list_profiles(PlatformKey.XHS)] == ["pf_first"]

    updated = first.model_copy(update={"profile_name": "Updated", "updated_at": now + timedelta(minutes=2)})
    repository.save_profile(updated)
    assert repository.get_profile("pf_first").profile_name == "Updated"

    assert repository.delete_profile("pf_second") is True
    assert repository.delete_profile("missing") is False
    assert [item.id for item in repository.list_profiles()] == ["pf_first"]
