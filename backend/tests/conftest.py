import sys
from pathlib import Path

import pytest
from sqlalchemy import text

# Make the backend directory importable so tests can import app.*
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from app.core.security import create_access_token, hash_password
from app.db.database import SessionLocal
from app.models import Subject, Concept, User, StudentProfile

TEST_PASSWORD = "pytest-password-1"


def ensure_account(username: str, role: str = "student") -> int:
    """Create (or reset) a test account with a known password; return id."""

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.username == username)
            .first()
        )

        if user is None:
            user = User(username=username)
            db.add(user)

        user.role = role
        user.is_active = True
        user.password_hash = hash_password(TEST_PASSWORD)
        db.commit()

        return user.id

    finally:
        db.close()


def token_for(username: str, role: str = "student") -> dict:
    """Authorization header for a test account."""

    user_id = ensure_account(username, role)

    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}


@pytest.fixture(autouse=True)
def _reset_login_throttle():
    from app.core import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture(autouse=True)
def _sign_in_module_client(request):
    """Sign the module-level ``client`` in as ``pytest_user``.

    Most test modules create ``client = TestClient(app)`` at import time.
    Signing it in here keeps those tests about the tutor, not about
    authentication. Modules that test authentication use their own
    clients and set headers explicitly.
    """

    client = getattr(request.module, "client", None)

    if client is not None:
        client.headers.update(token_for("pytest_user"))

    yield


@pytest.fixture
def test_student():
    db = SessionLocal()

    try:
        # Create the subject required by diagnostic tests.
        subject = (
            db.query(Subject)
            .filter(Subject.id == 1)
            .first()
        )

        if not subject:
            subject = Subject(
                id=1,
                name="Test Subject",
                description="Test subject for automated tests.",
            )
            db.add(subject)
            db.flush()

        # Create the concepts required by diagnostic tests.
        for concept_id, concept_name in [
            (1, "Test Concept 1"),
            (2, "Test Concept 2"),
        ]:
            concept = (
                db.query(Concept)
                .filter(Concept.id == concept_id)
                .first()
            )

            if not concept:
                db.add(
                    Concept(
                        id=concept_id,
                        subject_id=subject.id,
                        name=concept_name,
                        description="Test concept for automated tests.",
                    )
                )

        db.flush()

        # The rows above use explicit primary keys, which does not advance
        # the PostgreSQL id sequences. Without this, the next row created
        # normally (for example a subject added through the API) would
        # collide with id 1.
        for table in ("subjects", "concepts"):
            db.execute(
                text(
                    "SELECT setval("
                    f"pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 1) FROM {table})"
                    ")"
                )
            )

        # Create a test user.
        ensure_account("pytest_user")

        user = (
            db.query(User)
            .filter(User.username == "pytest_user")
            .one()
        )

        # Create the student's profile.
        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == user.id)
            .first()
        )

        if not profile:
            profile = StudentProfile(
                user_id=user.id,
                learning_level="beginner",
            )
            db.add(profile)
            db.flush()

        db.commit()
        db.refresh(profile)

        yield profile.id

    finally:
        db.close()