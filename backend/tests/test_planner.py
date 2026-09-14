from app.db.database import SessionLocal
from app.services.learning_planner import select_next_concept


def test_select_next_concept_returns_none_when_subject_is_mastered():
    db = SessionLocal()

    try:
        concept = select_next_concept(
            db=db,
            student_id=1,
            subject_id=1,
        )

        assert concept is None

    finally:
        db.close()