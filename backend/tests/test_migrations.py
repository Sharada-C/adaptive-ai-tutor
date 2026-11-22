"""Alembic must build the real schema from an empty database.

These tests create throw-away databases on the same server as the test
database, run Alembic in a subprocess (env.py reads DATABASE_URL), and
compare the result with ``Base.metadata.create_all``.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.schema_upgrade import upgrade_user_table
from app.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]


def _admin_engine():
    url = make_url(settings.database_url).set(database="postgres")
    return create_engine(url, isolation_level="AUTOCOMMIT")


@pytest.fixture
def scratch_db():
    name = f"mig_{uuid.uuid4().hex[:10]}"
    admin = _admin_engine()
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(settings.database_url).set(database=name)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            )
        admin.dispose()


def _alembic(url, *args):
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(REPO_ROOT / "alembic.ini"), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _shape(url):
    engine = create_engine(url)
    insp = inspect(engine)
    shape = {}
    for table in sorted(insp.get_table_names()):
        if table == "alembic_version":
            continue
        shape[table] = {
            "columns": sorted(
                (c["name"], str(c["type"]), c["nullable"])
                for c in insp.get_columns(table)
            ),
            "unique": sorted(
                tuple(u["column_names"]) for u in insp.get_unique_constraints(table)
            ),
            "fks": sorted(
                (tuple(f["constrained_columns"]), f["referred_table"])
                for f in insp.get_foreign_keys(table)
            ),
        }
    engine.dispose()
    return shape


def test_upgrade_head_on_empty_database(scratch_db):
    result = _alembic(scratch_db, "upgrade", "head")
    assert result.returncode == 0, result.stderr


def test_models_and_migrations_have_no_drift(scratch_db):
    up = _alembic(scratch_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    check = _alembic(scratch_db, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_migrated_schema_matches_create_all(scratch_db):
    up = _alembic(scratch_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    other = make_url(scratch_db).set(database=scratch_db.database + "_ca")
    admin = _admin_engine()
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{other.database}"'))
    try:
        engine = create_engine(other)
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(engine)
        engine.dispose()
        assert _shape(scratch_db) == _shape(other)
    finally:
        with admin.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{other.database}" WITH (FORCE)')
            )
        admin.dispose()


def test_legacy_database_stamped_at_old_revision_upgrades(scratch_db):
    """A dev DB built by create_tables.py and stamped 3623a8b541cc must
    still upgrade cleanly."""
    engine = create_engine(scratch_db)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    upgrade_user_table(engine)
    engine.dispose()

    stamp = _alembic(scratch_db, "stamp", "3623a8b541cc")
    assert stamp.returncode == 0, stamp.stderr
    up = _alembic(scratch_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    check = _alembic(scratch_db, "check")
    assert check.returncode == 0, check.stdout + check.stderr


def test_unique_mastery_migration_merges_existing_duplicates(scratch_db):
    """Duplicates created by the old race are merged, not rejected."""
    up = _alembic(scratch_db, "upgrade", "0002_auth_columns")
    assert up.returncode == 0, up.stderr

    engine = create_engine(scratch_db)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (username) VALUES ('u')"))
        conn.execute(
            text("INSERT INTO student_profiles (user_id, learning_level, created_at) "
                 "SELECT id, 'beginner', now() FROM users")
        )
        conn.execute(text("INSERT INTO subjects (name) VALUES ('s')"))
        conn.execute(
            text("INSERT INTO concepts (subject_id, name) SELECT id, 'c' FROM subjects")
        )
        for result in ("correct", "incorrect"):
            conn.execute(
                text(
                    "INSERT INTO assessment_attempts (student_id, concept_id, question, "
                    "student_answer, score, result, created_at) "
                    "SELECT p.id, c.id, 'q', 'a', 1, :r, now() "
                    "FROM student_profiles p, concepts c"
                ),
                {"r": result},
            )
        for _ in range(2):
            conn.execute(
                text(
                    "INSERT INTO concept_mastery (student_id, concept_id, mastery_score, "
                    "attempts, correct_answers) SELECT p.id, c.id, 0.5, 1, 1 "
                    "FROM student_profiles p, concepts c"
                )
            )

    up = _alembic(scratch_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT attempts, correct_answers FROM concept_mastery")
        ).all()
    engine.dispose()
    assert rows == [(2, 1)]


def test_old_role_check_constraint_is_removed_so_instructors_can_exist(scratch_db):
    """Databases from an abandoned early migration limit role to
    ('student', 'admin'); the 'instructor' role must still be storable."""
    up = _alembic(scratch_db, "upgrade", "0005_student_cascades")
    assert up.returncode == 0, up.stderr

    engine = create_engine(scratch_db)
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE users ADD CONSTRAINT ck_users_role "
                 "CHECK (role IN ('student', 'admin'))")
        )

    up = _alembic(scratch_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, role) VALUES ('teacher', 'instructor')")
        )
    engine.dispose()
