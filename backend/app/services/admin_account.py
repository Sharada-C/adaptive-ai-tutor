"""Create or promote an administrator account."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.student import StudentProfile, User


def ensure_admin(db: Session, username: str, password: str) -> User:
    """Create ``username`` as an admin, or promote it if it exists.

    The password of an existing account is only set when it has none, so
    restarting the server never overwrites a password that was changed.
    """

    user = (
        db.query(User)
        .filter(func.lower(User.username) == username.lower())
        .first()
    )

    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(user)
        db.flush()
        db.add(StudentProfile(user_id=user.id, learning_level="beginner"))

    else:
        user.role = "admin"
        user.is_active = True

        if not user.password_hash:
            user.password_hash = hash_password(password)

    db.commit()
    db.refresh(user)

    return user
