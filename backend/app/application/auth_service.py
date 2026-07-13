from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


logger = logging.getLogger(__name__)


class AuthRateLimitedError(Exception):
    """Raised when an account has too many recent failed login attempts."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Too many failed attempts; retry in {retry_after_seconds}s")

# Salted PBKDF2-HMAC-SHA256, encoded as "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>".
# The "$" delimiter keeps the value free of the ":" used by MEDIASPIDER_AUTH_USERS.
PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_DEFAULT_ITERATIONS = 260_000
_INSECURE_SECRETS = {"", "dev-only-change-me", "change-me"}


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
        self.max_attempts = int(os.getenv("MEDIASPIDER_AUTH_MAX_ATTEMPTS", "5"))
        self.lockout_seconds = int(os.getenv("MEDIASPIDER_AUTH_LOCKOUT_SECONDS", "300"))
        self._failed_attempts: dict[str, list[float]] = {}
        self.users = self._load_users()
        self._warn_on_insecure_config()

    def login(self, username: str, password: str) -> tuple[str, AuthUser]:
        self._enforce_rate_limit(username)
        user_record = self.users.get(username)
        if user_record is None or not self._verify_password(password, user_record["password"]):
            self._register_failure(username)
            raise ValueError("Invalid username or password")
        self._failed_attempts.pop(username, None)
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

    def _enforce_rate_limit(self, username: str) -> None:
        """Reject logins for an account with too many recent failures."""
        if self.max_attempts <= 0:
            return
        now = time.monotonic()
        recent = [ts for ts in self._failed_attempts.get(username, []) if now - ts < self.lockout_seconds]
        self._failed_attempts[username] = recent
        if len(recent) >= self.max_attempts:
            retry_after = int(self.lockout_seconds - (now - min(recent))) + 1
            logger.warning("Login rate limit hit for user %s", username)
            raise AuthRateLimitedError(max(retry_after, 1))

    def _register_failure(self, username: str) -> None:
        if self.max_attempts <= 0:
            return
        self._failed_attempts.setdefault(username, []).append(time.monotonic())

    @staticmethod
    def hash_password(password: str, *, iterations: int = PBKDF2_DEFAULT_ITERATIONS) -> str:
        """Produce a salted PBKDF2 hash string for MEDIASPIDER_AUTH_USERS."""
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"{PBKDF2_PREFIX}${iterations}${salt.hex()}${digest.hex()}"

    def _verify_password(self, candidate: str, expected: str) -> bool:
        if expected.startswith(f"{PBKDF2_PREFIX}$"):
            try:
                _, iterations_raw, salt_hex, hash_hex = expected.split("$", 3)
                iterations = int(iterations_raw)
                salt = bytes.fromhex(salt_hex)
                expected_digest = bytes.fromhex(hash_hex)
            except (ValueError, TypeError):
                return False
            candidate_digest = hashlib.pbkdf2_hmac("sha256", candidate.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(candidate_digest, expected_digest)
        # Backward-compatible plaintext comparison (constant-time). A startup
        # warning is emitted so operators migrate to hashed credentials.
        return hmac.compare_digest(candidate, expected)

    def _warn_on_insecure_config(self) -> None:
        if not self.auth_required:
            return
        if self.secret in _INSECURE_SECRETS:
            logger.warning(
                "MEDIASPIDER_AUTH_SECRET is unset or a default value; set a strong random secret in production."
            )
        plaintext_users = sorted(
            username
            for username, record in self.users.items()
            if not record["password"].startswith(f"{PBKDF2_PREFIX}$")
        )
        if plaintext_users:
            logger.warning(
                "Auth users store plaintext passwords: %s. Generate hashes with "
                "scripts/hash_password.py and put pbkdf2_sha256$... in MEDIASPIDER_AUTH_USERS.",
                ", ".join(plaintext_users),
            )
        if self.users.get("admin", {}).get("password") == "admin":
            logger.warning(
                "Default admin/admin credential is active; change it before exposing the service."
            )

    def _pad_base64(self, value: str) -> bytes:
        return (value + "=" * (-len(value) % 4)).encode("ascii")
