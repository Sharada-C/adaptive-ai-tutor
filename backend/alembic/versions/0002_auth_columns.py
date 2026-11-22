"""add auth columns to users

Revision ID: 0002_auth_columns
Revises: 3623a8b541cc
Create Date: 2026-11-21

Idempotent on purpose: databases created before Alembic was introduced
already received these columns from app/db/schema_upgrade.py.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002_auth_columns"
down_revision: Union[str, Sequence[str], None] = "3623a8b541cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) "
        "NOT NULL DEFAULT 'student'"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN "
        "NOT NULL DEFAULT true"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_lower "
        "ON users (lower(username))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_username_lower")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_hash")
