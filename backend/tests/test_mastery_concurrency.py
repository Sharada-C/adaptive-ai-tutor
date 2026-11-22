"""Concurrent /tutor/evaluate calls must not split or lose mastery data."""

import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.api import evaluation
from app.db.database import SessionLocal
from app.main import app
from app.models.student import (
    AssessmentAttempt,
    ConceptMastery,
    QuizQuestionRecord,
)
from tests.conftest import token_for

THREADS = 10


def _fake_grader(question, expected_answer, student_answer):
    # Hold every request here so they all reach the mastery read together.
    time.sleep(0.15)
    return {
        "score": 1.0,
        "result": "correct",
        "feedback": "ok",
        "misconception": None,
    }


def test_parallel_evaluations_produce_one_row_with_ten_attempts(
    monkeypatch, test_student
):
    monkeypatch.setattr(evaluation, "evaluate_answer", _fake_grader)

    headers = token_for("pytest_user")
    concept_id = 2

    db = SessionLocal()
    db.query(AssessmentAttempt).filter_by(
        student_id=test_student, concept_id=concept_id
    ).delete()
    db.query(ConceptMastery).filter_by(
        student_id=test_student, concept_id=concept_id
    ).delete()
    db.commit()
    db.close()

    db = SessionLocal()
    question_ids = []
    for i in range(THREADS):
        row = QuizQuestionRecord(
            student_id=test_student,
            concept_id=concept_id,
            question_text=f"q{i}",
            expected_answer="a",
        )
        db.add(row)
        db.flush()
        question_ids.append(row.id)
    db.commit()
    db.close()

    def submit(i):
        with TestClient(app) as c:
            return c.post(
                "/tutor/evaluate",
                headers=headers,
                json={
                    "student_id": test_student,
                    "question_id": question_ids[i],
                    "student_answer": f"a{i}",
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        statuses = list(pool.map(submit, range(THREADS)))

    db = SessionLocal()
    try:
        rows = (
            db.query(ConceptMastery)
            .filter_by(student_id=test_student, concept_id=concept_id)
            .all()
        )
        attempts_logged = (
            db.query(func.count(AssessmentAttempt.id))
            .filter_by(student_id=test_student, concept_id=concept_id)
            .scalar()
        )
    finally:
        db.close()

    assert statuses == [200] * THREADS
    assert attempts_logged == THREADS
    assert len(rows) == 1
    assert rows[0].attempts == THREADS
    assert rows[0].correct_answers == THREADS
