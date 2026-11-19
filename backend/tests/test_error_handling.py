from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import ensure_account, token_for

from app.db.database import SessionLocal
from app.models.student import (
    User,
    StudentProfile,
    DiagnosticSession,
    DiagnosticQuestion,
)
client = TestClient(app)


def test_diagnostic_start_invalid_student():
    # A student id that is not theirs (or does not exist) is refused.
    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": 999999,
            "subject_id": 1,
            "limit": 2,
        },
    )

    assert response.status_code == 403
def test_diagnostic_start_invalid_subject(test_student):
    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": test_student,
            "subject_id": 999999,
            "limit": 2,
        },
    )

    assert response.status_code == 404

def test_diagnostic_start_invalid_limit(test_student):
    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": test_student,
            "subject_id": 1,
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_student_cannot_submit_another_students_diagnostic_question(
    test_student,
):
    db = SessionLocal()
    other_student = None
    session = None
    question = None

    try:
        # Create a separate student profile.
        user = (
            db.query(User)
            .filter(User.username == "pytest_other_user")
            .first()
        )

        if user is None:
            ensure_account("pytest_other_user")
            user = (
                db.query(User)
                .filter(User.username == "pytest_other_user")
                .one()
            )

        other_student = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == user.id)
            .first()
        )

        if other_student is None:
            other_student = StudentProfile(
                user_id=user.id,
                learning_level="beginner",
            )
            db.add(other_student)
            db.flush()

        # Create a diagnostic session owned by test_student.
        session = DiagnosticSession(
            student_id=test_student,
            subject_id=1,
            status="in_progress",
        )
        db.add(session)
        db.flush()

        question = DiagnosticQuestion(
            session_id=session.id,
            concept_id=1,
            question="What is process management?",
            expected_answer="It manages processes.",
            evaluation_criteria='["Defines process management"]',
            misconception_guidance="Explain process management.",
        )
        db.add(question)
        db.commit()

        response = client.post(
            "/tutor/diagnostic/submit",
            # Signed in as the other student, so the request passes the
            # "is this your profile" check and reaches the question check.
            headers=token_for("pytest_other_user"),
            json={
                "student_id": other_student.id,
                "question_id": question.id,
                "student_answer": "My answer",
            },
        )

        assert response.status_code == 403
        assert (
            response.json()["detail"]
            == "This diagnostic question does not belong to the student."
        )

        db.refresh(question)
        assert question.answered is False

    finally:
        db.close()
