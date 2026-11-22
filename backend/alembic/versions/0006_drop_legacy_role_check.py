"""drop the legacy users.role check constraint

Revision ID: 0006_drop_legacy_role_check
Revises: 0005_student_cascades
Create Date: 2026-11-22

An early, abandoned migration limited users.role to ('student', 'admin').
Databases that received it reject the 'instructor' role. Valid roles are
enforced by the application, so the old constraint is removed if present.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006_drop_legacy_role_check"
down_revision: Union[str, Sequence[str], None] = "0005_student_cascades"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")


def downgrade() -> None:
    # The old constraint was a bug for the 'instructor' role; not restored.
    pass
