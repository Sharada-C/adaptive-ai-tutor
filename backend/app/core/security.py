"""Password hashing and signed access tokens.

Passwords use scrypt from the standard library (memory-hard, no extra
dependency). Tokens are HS256 JWTs signed with ``SECRET_KEY``.
"""

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

if settings.secret_key:
    _SECRET = settings.secret_key
else:
    _SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "SECRET_KEY is not set; using a random key. Logins will not "
        "survive a server restart. Set SECRET_KEY in .env."
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )

    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str | None) -> bool:
    """Check a password. Returns False for a missing or malformed hash."""

    if not stored:
        return False

    try:
        scheme, n, r, p, salt, digest = stored.split("$")

        if scheme != "scrypt":
            return False

        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
        )

    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(actual, expected)


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }

    return jwt.encode(payload, _SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Return the token payload, or None if invalid or expired."""

    try:
        return jwt.decode(token, _SECRET, algorithms=[ALGORITHM])

    except jwt.PyJWTError:
        return None
