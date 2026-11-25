"""private, student-created courses

Revision ID: 0007_private_student_courses
Revises: 0006_drop_legacy_role_check
Create Date: 2026-11-22

Adds subjects.owner_id (NULL = shared course, set = private to that user)
and relaxes name uniqueness: shared names stay globally unique, private
names only need to be unique per owner.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0007_private_student_courses"
down_revision: Union[str, Sequence[str], None] = "0006_drop_legacy_role_check"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE subjects ADD COLUMN IF NOT EXISTS owner_id INTEGER "
        "REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_subjects_owner_id ON subjects (owner_id)")
    op.execute("ALTER TABLE subjects DROP CONSTRAINT IF EXISTS subjects_name_key")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_subjects_shared_name "
        "ON subjects (name) WHERE owner_id IS NULL"
    )
    # Guarded: a database built by create_all() already has it.
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'uq_subjects_owner_name') THEN "
        "ALTER TABLE subjects ADD CONSTRAINT uq_subjects_owner_name "
        "UNIQUE (owner_id, name); END IF; END $$"
    )


def downgrade() -> None:
    # Private courses cannot satisfy the old global-unique name rule.
    op.execute("DELETE FROM subjects WHERE owner_id IS NOT NULL AND id NOT IN "
               "(SELECT DISTINCT subject_id FROM concepts)")
    op.execute("ALTER TABLE subjects DROP CONSTRAINT IF EXISTS uq_subjects_owner_name")
    op.execute("DROP INDEX IF EXISTS uq_subjects_shared_name")
    op.execute("DROP INDEX IF EXISTS ix_subjects_owner_id")
    op.execute("ALTER TABLE subjects DROP COLUMN IF EXISTS owner_id")
    op.execute("ALTER TABLE subjects ADD CONSTRAINT subjects_name_key UNIQUE (name)")
