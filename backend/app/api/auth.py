from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import STUDENT, get_current_user, get_db
from app.core import login_throttle
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.student import StudentProfile, User
from app.schemas.auth import (
    AuthUser,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# A real hash to compare against when the username does not exist, so a
# login takes the same time whether or not the account is there.
_DUMMY_HASH = hash_password("not-a-real-password")


def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "user": user,
    }


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Create a learner account.

    Public sign-up always creates a ``student``. Instructor and admin
    roles can only be granted by an admin.
    """

    taken = (
        db.query(User)
        .filter(func.lower(User.username) == request.username.lower())
        .first()
    )

    if taken:
        raise HTTPException(
            status_code=409,
            detail="That username is already taken.",
        )

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        role=STUDENT,
    )

    db.add(user)

    try:
        db.flush()
        db.add(StudentProfile(user_id=user.id, learning_level="beginner"))
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="That username is already taken.",
        ) from None

    db.refresh(user)

    return _token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    # Do not trust X-Forwarded-For: it is client-controlled unless a trusted
    # proxy overwrites it.
    client_ip = http_request.client.host if http_request.client else "unknown"

    wait = login_throttle.retry_after(request.username, client_ip)

    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    user = (
        db.query(User)
        .filter(
            func.lower(User.username) == request.username.strip().lower()
        )
        .first()
    )

    stored = user.password_hash if user else _DUMMY_HASH
    valid = verify_password(request.password, stored)

    if user is None or not valid:
        login_throttle.record_failure(request.username, client_ip)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account has been deactivated.",
        )

    login_throttle.record_success(request.username)

    return _token_response(user)


@router.get(
    "/me",
    response_model=AuthUser,
)
def me(current_user: User = Depends(get_current_user)):
    return current_user
