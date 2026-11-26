"""A concept must be answered well repeatedly before it counts as mastered."""

from app.db.database import SessionLocal
from app.models.student import AssessmentAttempt, ConceptMastery
from app.services.mastery_service import lock_mastery, refresh_mastery

ADVANCE = 0.80
CONCEPT_ID = 1


def _score_after(student_id: int, scores: list[float]) -> float:
    db = SessionLocal()

    try:
        db.query(AssessmentAttempt).filter_by(
            student_id=student_id, concept_id=CONCEPT_ID
        ).delete()
        db.query(ConceptMastery).filter_by(
            student_id=student_id, concept_id=CONCEPT_ID
        ).delete()
        db.commit()

        result = 0.0

        for score in scores:
            mastery = lock_mastery(db, student_id, CONCEPT_ID)
            db.add(
                AssessmentAttempt(
                    student_id=student_id,
                    concept_id=CONCEPT_ID,
                    question="q",
                    student_answer="a",
                    score=score,
                    result="correct" if score >= 0.8 else "incorrect",
                )
            )
            refresh_mastery(db, mastery)
            db.commit()
            result = mastery.mastery_score

        return result
    finally:
        db.close()


def test_one_correct_answer_is_not_mastery(test_student):
    assert _score_after(test_student, [1.0]) < ADVANCE


def test_two_correct_answers_reach_mastery(test_student):
    assert _score_after(test_student, [1.0, 1.0]) >= ADVANCE


def test_recent_mistakes_pull_the_score_down(test_student):
    assert _score_after(test_student, [1.0, 1.0, 0.0, 0.0]) < ADVANCE


def test_score_stays_within_bounds(test_student):
    score = _score_after(test_student, [1.0] * 8)

    assert 0.9 < score <= 1.0
