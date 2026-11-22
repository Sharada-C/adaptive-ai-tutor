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


def _relax_legacy_columns(connection, table: str) -> None:
    """Drop NOT NULL from columns the current model does not know about.

    An older version of this project may have created columns (for example
    ``users.created_at``) that are required but have no default. The
    current model never fills them, so every insert would fail. Making them
    nullable is non-destructive and keeps the data.
    """

    from app.models import Base

    known = set(Base.metadata.tables[table].columns.keys())

    rows = connection.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table "
            "AND is_nullable = 'NO' AND column_default IS NULL "
            "AND is_identity = 'NO'"
        ),
        {"table": table},
    ).scalars().all()

    for name in rows:
        if name in known:
            continue

        logger.warning("Making legacy column %s.%s nullable.", table, name)
        connection.execute(
            text(f'ALTER TABLE {table} ALTER COLUMN "{name}" DROP NOT NULL')
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

        _relax_legacy_columns(connection, "users")

        profiles = connection.execute(
            text("SELECT to_regclass('public.student_profiles')")
        ).scalar()

        if profiles is not None:
            _relax_legacy_columns(connection, "student_profiles")

    try:
        with engine.begin() as connection:
            connection.execute(text(_INDEX))

    except Exception:
        logger.warning(
            "Could not add the case-insensitive unique index on "
            "users.username; existing usernames differ only by case."
        )
