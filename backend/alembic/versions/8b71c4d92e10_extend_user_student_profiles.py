"""extend users and student profiles for accounts and personalization

Revision ID: 8b71c4d92e10
Revises: 3623a8b541cc
Create Date: 2026-11-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b71c4d92e10"
down_revision: Union[str, Sequence[str], None] = "3623a8b541cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable email first: existing accounts may not have an email yet.
    op.add_column(
        "users",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_users_email",
        "users",
        ["email"],
    )
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )

    # Existing accounts become students and remain active by default.
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="student",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('student', 'admin')",
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Profile additions are nullable or have safe defaults so existing
    # student_profiles rows and their foreign-key relationships are retained.
    op.add_column(
        "student_profiles",
        sa.Column("full_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "student_profiles",
        sa.Column(
            "learning_goals",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "student_profiles",
        sa.Column("learning_style", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "student_profiles",
        sa.Column(
            "interests",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "student_profiles",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Remove database-side defaults after backfilling existing rows.
    # SQLAlchemy supplies defaults for newly-created records.
    op.alter_column("users", "role", server_default=None)
    op.alter_column("users", "is_active", server_default=None)
    op.alter_column("users", "created_at", server_default=None)
    op.alter_column("student_profiles", "learning_goals", server_default=None)
    op.alter_column("student_profiles", "interests", server_default=None)
    op.alter_column("student_profiles", "updated_at", server_default=None)


def downgrade() -> None:
    # This migration's downgrade removes only the columns and constraints
    # introduced above. Existing user/profile rows and learning records remain.
    op.drop_column("student_profiles", "updated_at")
    op.drop_column("student_profiles", "interests")
    op.drop_column("student_profiles", "learning_style")
    op.drop_column("student_profiles", "learning_goals")
    op.drop_column("student_profiles", "full_name")

    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email")
