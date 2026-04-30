from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .base import TimestampedModel, generate_id


class PlatformKey(str, Enum):
    XHS = "xhs"
    DY = "dy"
    KS = "ks"
    BILI = "bili"
    WB = "wb"
    TIEBA = "tieba"
    ZHIHU = "zhihu"
    XIANYU = "xianyu"


class AuthType(str, Enum):
    QRCODE = "qrcode"
    COOKIE = "cookie"
    PHONE = "phone"
    STATE_FILE = "state_file"


class PlatformProfile(TimestampedModel):
    id: str = Field(default_factory=lambda: generate_id("pf"))
    platform: PlatformKey
    profile_name: str
    auth_type: AuthType
    credentials_ref: str = ""
    settings_json: dict = Field(default_factory=dict)
