import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH


_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,49}$")

Role = Literal["student", "instructor", "admin"]


def _check_username(value: str) -> str:
    value = value.strip()

    if not _USERNAME_RE.match(value):
        raise ValueError(
            "Username must be 3-50 characters: letters, numbers, dots, "
            "dashes or underscores, starting with a letter or number."
        )

    return value


def _check_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
        )

    return value


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _username(cls, value):
        return _check_username(value)

    @field_validator("password")
    @classmethod
    def _password(cls, value):
        return _check_password(value)


class LoginRequest(BaseModel):
    # Not validated beyond presence: a login should fail with the same
    # message whatever is wrong, not reveal the username rules.
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class AuthUser(BaseModel):
    id: int
    username: str
    role: Role

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class AdminUserResponse(AuthUser):
    is_active: bool
    has_password: bool


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def _password(cls, value):
        return None if value is None else _check_password(value)
