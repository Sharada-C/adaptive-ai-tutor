"""one mastery row per student and concept

Revision ID: 0003_unique_mastery
Revises: 0002_auth_columns
Create Date: 2026-11-21

Concurrent requests could create several concept_mastery rows for the same
(student, concept). Before adding the unique constraint, duplicates are
merged: the lowest id is kept and its counters are recomputed from the
assessment_attempts history (the source of truth); the others are deleted.
Mastery rows are derived data, so nothing a student typed is lost.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_unique_mastery"
down_revision: Union[str, Sequence[str], None] = "0002_auth_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE concept_mastery m
        SET attempts = COALESCE(a.n, m.attempts),
            correct_answers = COALESCE(a.c, m.correct_answers)
        FROM (
            SELECT student_id, concept_id,
                   COUNT(*) AS n,
                   COUNT(*) FILTER (WHERE result = 'correct') AS c
            FROM assessment_attempts
            GROUP BY student_id, concept_id
        ) a
        WHERE a.student_id = m.student_id
          AND a.concept_id = m.concept_id
          AND m.id IN (
              SELECT MIN(id) FROM concept_mastery GROUP BY student_id, concept_id
              HAVING COUNT(*) > 1
          )
        """
    )
    op.execute(
        """
        DELETE FROM concept_mastery
        WHERE id NOT IN (
            SELECT MIN(id) FROM concept_mastery GROUP BY student_id, concept_id
        )
        """
    )
    # Skip when create_all() already built the constraint (databases made by
    # create_tables.py after this change and then stamped).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_student_concept_mastery'
            ) THEN
                ALTER TABLE concept_mastery
                ADD CONSTRAINT uq_student_concept_mastery
                UNIQUE (student_id, concept_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_student_concept_mastery", "concept_mastery", type_="unique"
    )
