from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str
    display_name: str


class AuthService:
    def __init__(self) -> None:
        self.secret = os.getenv("MEDIASPIDER_AUTH_SECRET", "dev-only-change-me")
        self.token_ttl_minutes = int(os.getenv("MEDIASPIDER_AUTH_TOKEN_TTL_MINUTES", "720"))
        self.auth_required = os.getenv("MEDIASPIDER_AUTH_REQUIRED", "false").lower() == "true"
        self.users = self._load_users()

    def login(self, username: str, password: str) -> tuple[str, AuthUser]:
        user_record = self.users.get(username)
        if user_record is None or not self._verify_password(password, user_record["password"]):
            raise ValueError("Invalid username or password")
        user = AuthUser(
            username=username,
            role=user_record["role"],
            display_name=user_record.get("display_name") or username,
        )
        return self.create_token(user), user

    def create_token(self, user: AuthUser) -> str:
        expires_at = datetime.utcnow() + timedelta(minutes=self.token_ttl_minutes)
        payload = {
            "sub": user.username,
            "role": user.role,
            "name": user.display_name,
            "exp": int(expires_at.timestamp()),
            "nonce": secrets.token_hex(8),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
        signature = self._sign(encoded_payload)
        return f"{encoded_payload}.{signature}"

    def verify_token(self, token: str) -> AuthUser:
        try:
            encoded_payload, signature = token.split(".", 1)
        except ValueError as exc:
            raise ValueError("Invalid token") from exc
        expected_signature = self._sign(encoded_payload)
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature")
        payload = json.loads(base64.urlsafe_b64decode(self._pad_base64(encoded_payload)).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.utcnow().timestamp()):
            raise ValueError("Token expired")
        username = str(payload.get("sub") or "")
        if username not in self.users:
            raise ValueError("Unknown user")
        return AuthUser(
            username=username,
            role=str(payload.get("role") or self.users[username]["role"]),
            display_name=str(payload.get("name") or username),
        )

    def user_has_role(self, user: AuthUser, allowed_roles: Iterable[str]) -> bool:
        roles = set(allowed_roles)
        if not roles:
            return True
        if user.role == "admin":
            return True
        return user.role in roles

    def anonymous_user(self) -> AuthUser:
        return AuthUser(username="anonymous", role="admin", display_name="Development User")

    def _sign(self, encoded_payload: str) -> str:
        digest = hmac.new(self.secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def _load_users(self) -> dict[str, dict[str, str]]:
        raw = os.getenv("MEDIASPIDER_AUTH_USERS", "")
        if not raw:
            return {
                "admin": {
                    "password": "admin",
                    "role": "admin",
                    "display_name": "Administrator",
                }
            }
        users: dict[str, dict[str, str]] = {}
        for entry in raw.split(","):
            parts = [part.strip() for part in entry.split(":")]
            if len(parts) < 3 or not parts[0]:
                continue
            username, password, role = parts[:3]
            users[username] = {
                "password": password,
                "role": role,
                "display_name": parts[3] if len(parts) > 3 else username,
            }
        return users

    def _verify_password(self, candidate: str, expected: str) -> bool:
        return hmac.compare_digest(candidate, expected)

    def _pad_base64(self, value: str) -> bytes:
        return (value + "=" * (-len(value) % 4)).encode("ascii")
