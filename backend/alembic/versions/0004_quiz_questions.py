"""store quiz questions server-side

Revision ID: 0004_quiz_questions
Revises: 0003_unique_mastery
Create Date: 2026-11-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_quiz_questions"
down_revision: Union[str, Sequence[str], None] = "0003_unique_mastery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Databases built by create_all() and then stamped already have the table.
    if sa.inspect(op.get_bind()).has_table("quiz_questions"):
        return

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.String(length=30), nullable=True),
        sa.Column(
            "answered",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quiz_questions_student_id"),
        "quiz_questions",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quiz_questions_student_id"), table_name="quiz_questions")
    op.drop_table("quiz_questions")
