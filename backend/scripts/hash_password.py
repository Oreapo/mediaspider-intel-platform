"""Generate a PBKDF2 password hash for MEDIASPIDER_AUTH_USERS.

Usage:
    python backend/scripts/hash_password.py            # prompt for the password
    python backend/scripts/hash_password.py 's3cret!'  # hash the given password

Paste the printed value in place of the plaintext password, e.g.
    MEDIASPIDER_AUTH_USERS=analyst:pbkdf2_sha256$260000$<salt>$<hash>:analyst:Risk Analyst
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.auth_service import AuthService


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm: "):
            print("Passwords do not match.", file=sys.stderr)
            raise SystemExit(1)
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        raise SystemExit(1)
    print(AuthService.hash_password(password))


if __name__ == "__main__":
    main()
