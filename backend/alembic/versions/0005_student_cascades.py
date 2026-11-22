"""cascade deletes for student-owned records

Revision ID: 0005_student_cascades
Revises: 0004_quiz_questions
Create Date: 2026-11-22

Deleting a user now removes their profile, and deleting a profile removes
their attempts, mastery, misconceptions, diagnostics and quiz questions.
Shared content is deliberately NOT cascaded: a subject with concepts, or a
concept with student history, still cannot be deleted by accident.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005_student_cascades"
down_revision: Union[str, Sequence[str], None] = "0004_quiz_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, referenced table)
CASCADES = [
    ("student_profiles", "user_id", "users"),
    ("assessment_attempts", "student_id", "student_profiles"),
    ("concept_mastery", "student_id", "student_profiles"),
    ("misconceptions", "student_id", "student_profiles"),
    ("diagnostic_sessions", "student_id", "student_profiles"),
    ("diagnostic_questions", "session_id", "diagnostic_sessions"),
    ("quiz_questions", "student_id", "student_profiles"),
]


def _recreate(ondelete: str | None) -> None:
    for table, column, referred in CASCADES:
        name = f"{table}_{column}_fkey"
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, referred, [column], ["id"], ondelete=ondelete
        )


def upgrade() -> None:
    _recreate("CASCADE")


def downgrade() -> None:
    _recreate(None)
