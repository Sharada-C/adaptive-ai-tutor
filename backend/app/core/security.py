
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


# Initialize Argon2 password hashing
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Convert a plain-text password into a secure Argon2 hash.
    """
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify whether the supplied password matches the stored hash.
    """
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.
    """
    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes
        )

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode.update({
        "exp": expire,
    })

    token = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    return token


def verify_access_token(token: str) -> dict | None:
    """
    Decode and verify a JWT token.

    Returns the token payload if valid.
    Returns None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
        return payload

    except jwt.InvalidTokenError:
        return None
