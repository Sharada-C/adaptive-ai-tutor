"""Shared FastAPI dependencies: database session, current user, roles."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import SessionLocal
from app.models.student import StudentProfile, User


STUDENT = "student"
INSTRUCTOR = "instructor"
ADMIN = "admin"

ROLES = (STUDENT, INSTRUCTOR, ADMIN)
STAFF_ROLES = (INSTRUCTOR, ADMIN)

_bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized("Sign in to continue.")

    payload = decode_access_token(credentials.credentials)

    if payload is None:
        raise _unauthorized("Your session has expired. Sign in again.")

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise _unauthorized("Your session is invalid. Sign in again.")

    user = db.get(User, user_id)

    # The role is read from the database on every request, so a role
    # change or deactivation takes effect immediately instead of when
    # the token expires.
    if user is None or not user.is_active:
        raise _unauthorized("This account is not available.")

    return user


def require_roles(*roles: str):
    """Dependency that only lets users with one of ``roles`` through."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to do that.",
            )

        return user

    return checker


require_staff = require_roles(*STAFF_ROLES)
require_admin = require_roles(ADMIN)


def ensure_student_access(
    db: Session,
    user: User,
    student_id: int,
    *,
    allow_staff: bool = False,
) -> StudentProfile:
    """Return the student profile if ``user`` may use it.

    Students (and everyone, for actions taken as the learner) can only
    touch their own profile. With ``allow_staff`` instructors and admins
    may also read any learner's data.
    """

    profile = db.get(StudentProfile, student_id)
    is_staff = allow_staff and user.role in STAFF_ROLES

    if profile is None:
        if is_staff:
            raise HTTPException(
                status_code=404,
                detail="Student profile not found",
            )

        # Do not reveal which ids exist to people who cannot see them.
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to do that.",
        )

    if profile.user_id != user.id and not is_staff:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to do that.",
        )

    return profile
