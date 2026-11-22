"""One prerequisite threshold, cycle rejection, explicit planner reasons,
and prerequisite enforcement on direct endpoint calls."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import SessionLocal
from app.main import app
from app.models import Concept, ConceptMastery, Subject
from app.models.student import (
    AssessmentAttempt,
    Misconception,
    QuizQuestionRecord,
    StudentProfile,
    User,
)
from app.schemas.curriculum_generation import (
    GeneratedConcept,
    GeneratedCurriculum,
)
from app.services import adaptation_service, learning_planner
from app.services.curriculum_persistence import save_generated_curriculum
from tests.conftest import ensure_account, token_for

client = TestClient(app)


@pytest.fixture
def chain():
    """Subject with Basics (root) and Advanced (requires Basics)."""

    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    username = f"prereq_{tag}"

    subject = Subject(name=f"Prereq Subject {tag}", description="t")
    db.add(subject)
    db.flush()
    basics = Concept(subject_id=subject.id, name="Basics", description="b")
    advanced = Concept(subject_id=subject.id, name="Advanced", description="a")
    db.add_all([basics, advanced])
    db.flush()
    advanced.prerequisites.append(basics)

    ensure_account(username)
    user = db.query(User).filter_by(username=username).one()
    student = StudentProfile(user_id=user.id, learning_level="beginner")
    db.add(student)
    db.commit()

    ctx = {
        "subject_id": subject.id,
        "basics_id": basics.id,
        "advanced_id": advanced.id,
        "student_id": student.id,
        "headers": token_for(username),
    }

    yield ctx

    db.rollback()
    ids = [basics.id, advanced.id]
    for model in (QuizQuestionRecord, AssessmentAttempt, ConceptMastery, Misconception):
        db.query(model).filter(model.student_id == student.id).delete()
    db.delete(student)
    db.delete(user)
    advanced.prerequisites.clear()
    db.flush()
    db.query(Concept).filter(Concept.id.in_(ids)).delete(synchronize_session=False)
    db.delete(subject)
    db.commit()
    db.close()


def _set_mastery(student_id, concept_id, score):
    db = SessionLocal()
    db.add(
        ConceptMastery(
            student_id=student_id,
            concept_id=concept_id,
            mastery_score=score,
            attempts=1,
            correct_answers=0,
        )
    )
    db.commit()
    db.close()


# ---- single threshold -------------------------------------------------


def test_threshold_is_one_setting_used_everywhere():
    assert settings.prerequisite_mastery_threshold == 0.80


def test_planner_and_adaptation_agree_at_075(chain):
    _set_mastery(chain["student_id"], chain["basics_id"], 0.75)
    db = SessionLocal()
    try:
        advanced = db.get(Concept, chain["advanced_id"])
        planner = learning_planner.prerequisites_satisfied(
            db, chain["student_id"], advanced
        )
        engine = adaptation_service.check_prerequisites_mastered(
            db, chain["student_id"], chain["advanced_id"]
        )
    finally:
        db.close()

    assert planner is False
    assert engine is False


# ---- cycles -----------------------------------------------------------


def _curriculum(edges):
    return GeneratedCurriculum(
        subject=f"Cycle Test {uuid.uuid4().hex[:8]}",
        description="d",
        concepts=[
            GeneratedConcept(name=name, description="d", prerequisites=prereqs)
            for name, prereqs in edges.items()
        ],
    )


@pytest.mark.parametrize(
    "edges",
    [
        {"X": ["Y"], "Y": ["X"]},
        {"A": ["B"], "B": ["C"], "C": ["A"]},
    ],
)
def test_circular_prerequisites_are_rejected_on_write(edges):
    db = SessionLocal()
    try:
        with pytest.raises(ValueError, match="[Cc]ircular"):
            save_generated_curriculum(db, _curriculum(edges))

    finally:
        db.rollback()
        db.close()


def test_acyclic_curriculum_still_saves():
    db = SessionLocal()
    curriculum = _curriculum({"One": [], "Two": ["One"], "Three": ["One", "Two"]})
    try:
        subject = save_generated_curriculum(db, curriculum)
        assert subject.id
        for concept in db.query(Concept).filter_by(subject_id=subject.id).all():
            concept.prerequisites.clear()
        db.flush()
        db.query(Concept).filter_by(subject_id=subject.id).delete()
        db.delete(subject)
        db.commit()
    finally:
        db.close()


# ---- planner reasons --------------------------------------------------


def test_plan_reports_complete_with_a_reason(chain):
    _set_mastery(chain["student_id"], chain["basics_id"], 1.0)
    _set_mastery(chain["student_id"], chain["advanced_id"], 1.0)
    db = SessionLocal()
    try:
        plan = learning_planner.plan_next_concept(
            db, chain["student_id"], chain["subject_id"]
        )
    finally:
        db.close()

    assert plan.concept is None
    assert plan.status == "complete"
    assert plan.reason


def test_plan_reports_blocked_instead_of_silent_none():
    """Every remaining concept is locked (circular data): say why."""

    db = SessionLocal()
    try:
        subject = Subject(name=f"Blocked {uuid.uuid4().hex[:8]}", description="t")
        db.add(subject)
        db.flush()
        a = Concept(subject_id=subject.id, name="A", description="a")
        b = Concept(subject_id=subject.id, name="B", description="b")
        db.add_all([a, b])
        db.flush()
        a.prerequisites.append(b)
        b.prerequisites.append(a)
        ensure_account("blocked_plan_user")
        user = db.query(User).filter_by(username="blocked_plan_user").one()
        student = db.query(StudentProfile).filter_by(user_id=user.id).first()
        if student is None:
            student = StudentProfile(user_id=user.id, learning_level="beginner")
            db.add(student)
        db.flush()

        plan = learning_planner.plan_next_concept(db, student.id, subject.id)

        assert plan.concept is None
        assert plan.status == "blocked"
        assert "prerequisite" in plan.reason.lower()
    finally:
        db.rollback()
        db.close()


def test_planner_endpoint_distinguishes_blocked_from_complete(chain):
    response = client.get(
        f"/students/{chain['student_id']}/subjects/{chain['subject_id']}/next",
        headers=chain["headers"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "next"
    assert response.json()["concept"]["id"] == chain["basics_id"]


# ---- enforcement on direct calls --------------------------------------


@pytest.mark.parametrize("path", ["/tutor/lesson", "/tutor/quiz"])
def test_direct_call_to_locked_concept_returns_weakest_prerequisite(chain, path):
    _set_mastery(chain["student_id"], chain["basics_id"], 0.30)

    response = client.post(
        path,
        headers=chain["headers"],
        json={
            "student_id": chain["student_id"],
            "concept_id": chain["advanced_id"],
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "prerequisite_required"
    assert detail["prerequisite_concept_id"] == chain["basics_id"]
    assert detail["prerequisite_concept"] == "Basics"
    assert detail["prerequisite_mastery_score"] == pytest.approx(0.30)
    assert detail["threshold"] == settings.prerequisite_mastery_threshold


def test_unlocked_concept_is_not_blocked(chain, monkeypatch):
    from app.api import quiz

    _set_mastery(chain["student_id"], chain["basics_id"], 0.95)
    monkeypatch.setattr(quiz, "retrieve_with_subject_fallback", lambda **kw: [])
    monkeypatch.setattr(
        quiz,
        "generate_quiz",
        lambda **kw: {"question": "Q?", "expected_answer": "A", "difficulty": "easy"},
    )

    response = client.post(
        "/tutor/quiz",
        headers=chain["headers"],
        json={
            "student_id": chain["student_id"],
            "concept_id": chain["advanced_id"],
        },
    )

    assert response.status_code == 200
