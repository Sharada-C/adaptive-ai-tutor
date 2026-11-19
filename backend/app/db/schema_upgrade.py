"""Bring an existing database up to date with the User model.

``Base.metadata.create_all`` creates missing tables but never alters
existing ones, so a database created before authentication was added has
a ``users`` table without the new columns. These statements are
idempotent and run at start-up and from ``create_tables.py``.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine


logger = logging.getLogger(__name__)

_COLUMNS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
    (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role "
        "VARCHAR(20) NOT NULL DEFAULT 'student'"
    ),
    (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active "
        "BOOLEAN NOT NULL DEFAULT true"
    ),
]

_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_lower "
    "ON users (lower(username))"
)


def upgrade_user_table(engine: Engine) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text("SELECT to_regclass('public.users')")
        ).scalar()

        if exists is None:
            return

        for statement in _COLUMNS:
            connection.execute(text(statement))

    try:
        with engine.begin() as connection:
            connection.execute(text(_INDEX))

    except Exception:
        logger.warning(
            "Could not add the case-insensitive unique index on "
            "users.username; existing usernames differ only by case."
        )
