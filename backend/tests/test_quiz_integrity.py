"""Grading must use the answer the server stored, never one from the client."""

from fastapi.testclient import TestClient

from app.api import evaluation, quiz
from app.db.database import SessionLocal
from app.main import app
from app.models.student import QuizQuestionRecord
from tests.conftest import ensure_account, token_for

client = TestClient(app)

STORED_ANSWER = "The kernel schedules processes."


def _store_question(student_id, concept_id=1):
    db = SessionLocal()
    try:
        row = QuizQuestionRecord(
            student_id=student_id,
            concept_id=concept_id,
            question_text="What does the scheduler do?",
            expected_answer=STORED_ANSWER,
            difficulty="easy",
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _spy(monkeypatch):
    seen = {}

    def fake(question, expected_answer, student_answer):
        seen.update(
            question=question,
            expected_answer=expected_answer,
            student_answer=student_answer,
        )
        return {
            "score": 0.0,
            "result": "incorrect",
            "feedback": "no",
            "misconception": None,
        }

    monkeypatch.setattr(evaluation, "evaluate_answer", fake)
    return seen


def test_tampered_expected_answer_is_ignored(monkeypatch, test_student):
    seen = _spy(monkeypatch)
    question_id = _store_question(test_student)

    response = client.post(
        "/tutor/evaluate",
        headers=token_for("pytest_user"),
        json={
            "student_id": test_student,
            "question_id": question_id,
            "student_answer": "Whatever I like",
            # A forged payload: all of these must be ignored.
            "expected_answer": "Whatever I like",
            "question": "A different question",
            "concept_id": 2,
        },
    )

    assert response.status_code == 200
    assert seen["expected_answer"] == STORED_ANSWER
    assert seen["question"] == "What does the scheduler do?"
    assert response.json()["result"] == "incorrect"


def test_question_response_never_contains_the_answer(monkeypatch, test_student):
    monkeypatch.setattr(
        quiz,
        "generate_quiz",
        lambda **kwargs: {
            "question": "Q?",
            "expected_answer": "SECRET",
            "difficulty": "easy",
        },
    )
    monkeypatch.setattr(
        quiz, "retrieve_with_subject_fallback", lambda **kwargs: []
    )

    response = client.post(
        "/tutor/quiz",
        headers=token_for("pytest_user"),
        json={"student_id": test_student, "concept_id": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert "SECRET" not in response.text
    assert "expected_answer" not in body
    assert isinstance(body["question_id"], int)
    assert body["question"] == "Q?"


def test_cannot_grade_another_students_question(monkeypatch, test_student):
    _spy(monkeypatch)
    db = SessionLocal()
    from app.models.student import StudentProfile, User

    ensure_account("quiz_other_owner")
    other_user = db.query(User).filter_by(username="quiz_other_owner").one()
    other = db.query(StudentProfile).filter_by(user_id=other_user.id).first()
    if other is None:
        other = StudentProfile(user_id=other_user.id, learning_level="beginner")
        db.add(other)
        db.commit()
    other_id = other.id
    db.close()

    question_id = _store_question(other_id)

    response = client.post(
        "/tutor/evaluate",
        headers=token_for("pytest_user"),
        json={
            "student_id": test_student,
            "question_id": question_id,
            "student_answer": "x",
        },
    )

    assert response.status_code == 404


def test_a_question_can_only_be_answered_once(monkeypatch, test_student):
    _spy(monkeypatch)
    question_id = _store_question(test_student)
    payload = {
        "student_id": test_student,
        "question_id": question_id,
        "student_answer": "x",
    }
    headers = token_for("pytest_user")

    assert client.post("/tutor/evaluate", headers=headers, json=payload).status_code == 200
    assert client.post("/tutor/evaluate", headers=headers, json=payload).status_code == 409
