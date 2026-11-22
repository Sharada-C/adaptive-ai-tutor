from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_db, require_admin
from app.core.security import hash_password
from app.models.student import User
from app.schemas.auth import AdminUserResponse, AdminUserUpdate


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "has_password": bool(user.password_hash),
    }


def _active_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == ADMIN, User.is_active.is_(True))
        .count()
    )


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
)
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.id).all()

    return [_serialize(user) for user in users]


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
)
def update_user(
    user_id: int,
    update: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    demoting = update.role is not None and update.role != ADMIN
    deactivating = update.is_active is False

    if user.role == ADMIN and (demoting or deactivating):
        # Never leave the system without a working administrator.
        if user.id == admin.id or _active_admin_count(db) <= 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You cannot demote or deactivate the last "
                    "administrator, or your own admin account."
                ),
            )

    if update.role is not None:
        user.role = update.role

    if update.is_active is not None:
        user.is_active = update.is_active

    if update.password is not None:
        user.password_hash = hash_password(update.password)

    db.commit()
    db.refresh(user)

    return _serialize(user)
