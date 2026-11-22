"""Deleting a student removes their records; shared content is protected."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.models import Concept, ConceptMastery, Subject
from app.models.student import (
    AssessmentAttempt,
    DiagnosticQuestion,
    DiagnosticSession,
    Misconception,
    QuizQuestionRecord,
    StudentProfile,
    User,
)

STUDENT_TABLES = [
    "assessment_attempts",
    "concept_mastery",
    "misconceptions",
    "diagnostic_sessions",
    "diagnostic_questions",
    "quiz_questions",
]


def _build(db):
    tag = uuid.uuid4().hex[:8]
    subject = Subject(name=f"Cascade {tag}", description="t")
    db.add(subject)
    db.flush()
    concept = Concept(subject_id=subject.id, name="C", description="c")
    user = User(username=f"cascade_{tag}")
    db.add_all([concept, user])
    db.flush()
    student = StudentProfile(user_id=user.id, learning_level="beginner")
    db.add(student)
    db.flush()
    sid, cid = student.id, concept.id
    db.add_all(
        [
            AssessmentAttempt(student_id=sid, concept_id=cid, question="q",
                              student_answer="a", score=1.0, result="correct"),
            ConceptMastery(student_id=sid, concept_id=cid, mastery_score=1.0,
                           attempts=1, correct_answers=1),
            Misconception(student_id=sid, concept_id=cid, description="m"),
            QuizQuestionRecord(student_id=sid, concept_id=cid, question_text="q",
                               expected_answer="a"),
        ]
    )
    session = DiagnosticSession(student_id=sid, subject_id=subject.id, status="open")
    db.add(session)
    db.flush()
    db.add(
        DiagnosticQuestion(session_id=session.id, concept_id=cid, question="q",
                           expected_answer="a", evaluation_criteria="[]")
    )
    db.commit()
    return subject, concept, user, student


def _count(db, student_id):
    counts = {}
    for table in ("assessment_attempts", "concept_mastery", "misconceptions",
                  "diagnostic_sessions", "quiz_questions"):
        counts[table] = db.execute(
            text(f"SELECT count(*) FROM {table} WHERE student_id = :s"), {"s": student_id}
        ).scalar()
    counts["diagnostic_questions"] = db.execute(
        text("SELECT count(*) FROM diagnostic_questions q JOIN diagnostic_sessions s "
             "ON s.id = q.session_id WHERE s.student_id = :s"),
        {"s": student_id},
    ).scalar()
    return counts


def test_deleting_a_student_removes_all_their_records():
    db = SessionLocal()
    subject, concept, user, student = _build(db)
    student_id, user_id, subject_id, concept_id = student.id, user.id, subject.id, concept.id
    assert all(n == 1 for n in _count(db, student_id).values())

    db.execute(text("DELETE FROM student_profiles WHERE id = :i"), {"i": student_id})
    db.commit()

    assert all(n == 0 for n in _count(db, student_id).values())

    # tidy up the shared rows the test created
    db.execute(text("DELETE FROM users WHERE id = :i"), {"i": user_id})
    db.execute(text("DELETE FROM concepts WHERE id = :i"), {"i": concept_id})
    db.execute(text("DELETE FROM subjects WHERE id = :i"), {"i": subject_id})
    db.commit()
    db.close()


def test_deleting_a_user_removes_their_profile_and_everything_under_it():
    db = SessionLocal()
    subject, concept, user, student = _build(db)
    student_id, user_id, subject_id, concept_id = student.id, user.id, subject.id, concept.id

    db.execute(text("DELETE FROM users WHERE id = :i"), {"i": user_id})
    db.commit()

    assert db.execute(
        text("SELECT count(*) FROM student_profiles WHERE id = :i"), {"i": student_id}
    ).scalar() == 0
    assert all(n == 0 for n in _count(db, student_id).values())

    db.execute(text("DELETE FROM concepts WHERE id = :i"), {"i": concept_id})
    db.execute(text("DELETE FROM subjects WHERE id = :i"), {"i": subject_id})
    db.commit()
    db.close()


def test_a_subject_with_concepts_cannot_be_deleted():
    db = SessionLocal()
    subject, concept, user, student = _build(db)
    ids = (subject.id, concept.id, user.id, student.id)

    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM subjects WHERE id = :i"), {"i": ids[0]})
    db.rollback()

    db.execute(text("DELETE FROM users WHERE id = :i"), {"i": ids[2]})
    db.execute(text("DELETE FROM concepts WHERE id = :i"), {"i": ids[1]})
    db.execute(text("DELETE FROM subjects WHERE id = :i"), {"i": ids[0]})
    db.commit()
    db.close()


def test_a_concept_with_student_history_cannot_be_deleted():
    db = SessionLocal()
    subject, concept, user, student = _build(db)
    ids = (subject.id, concept.id, user.id)

    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM concepts WHERE id = :i"), {"i": ids[1]})
    db.rollback()

    db.execute(text("DELETE FROM users WHERE id = :i"), {"i": ids[2]})
    db.execute(text("DELETE FROM concepts WHERE id = :i"), {"i": ids[1]})
    db.execute(text("DELETE FROM subjects WHERE id = :i"), {"i": ids[0]})
    db.commit()
    db.close()
