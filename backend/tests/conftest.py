import sys
from pathlib import Path

import pytest

# Make the backend directory importable so tests can import app.*
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from app.db.database import SessionLocal
from app.models import Subject, Concept, User, StudentProfile


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

        # Create a test user.
        user = (
            db.query(User)
            .filter(User.username == "pytest_user")
            .first()
        )

        if not user:
            user = User(
                username="pytest_user",
            )
            db.add(user)
            db.flush()

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