import sys
from pathlib import Path

import pytest

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
        subject = db.query(Subject).filter(Subject.id == 1).first()

        if not subject:
            subject = Subject(
                id=1,
                name="Test Subject",
                description="Test subject for automated tests.",
            )
            db.add(subject)
            db.flush()

        concept = db.query(Concept).filter(Concept.id == 1).first()

        if not concept:
            concept = Concept(
                id=1,
                subject_id=subject.id,
                name="Test Concept",
                description="Test concept for automated tests.",
            )
            db.add(concept)
            db.flush()

        user = db.query(User).filter(
            User.username == "pytest_user"
        ).first()

        if not user:
            user = User(username="pytest_user")
            db.add(user)
            db.flush()

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