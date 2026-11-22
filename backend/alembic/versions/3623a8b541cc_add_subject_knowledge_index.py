"""add subject knowledge index

Revision ID: 3623a8b541cc
Revises: 0001_baseline
Create Date: 2026-05-01

This was the original root revision. It could not run on an empty database
because it indexed a table that no migration created. It now sits after the
baseline; databases already stamped at this revision are unaffected.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "3623a8b541cc"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_knowledge_chunks_subject_id",
        "knowledge_chunks",
        ["subject_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_subject_id", table_name="knowledge_chunks")
