"""The learner's library of courses and the journal of what they learned."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.models import Concept, Subject
from app.models.student import (
    AssessmentAttempt,
    ConceptMastery,
    Misconception,
    QuizQuestionRecord,
    StudentProfile,
    User,
)
from tests.conftest import ensure_account, token_for

client = TestClient(app)


@pytest.fixture
def learner():
    tag = uuid.uuid4().hex[:8]
    names = {"me": f"lib_me_{tag}", "other": f"lib_other_{tag}"}
    db = SessionLocal()
    people = {}

    for key, name in names.items():
        ensure_account(name)
        user = db.query(User).filter_by(username=name).one()
        profile = StudentProfile(user_id=user.id, learning_level="beginner")
        db.add(profile)
        db.flush()
        people[key] = {"user": user.id, "student": profile.id, "headers": token_for(name)}

    mine = Subject(name=f"Mine {tag}", description="d", owner_id=people["me"]["user"])
    untouched = Subject(name=f"Untouched {tag}", description="d")
    theirs = Subject(name=f"Theirs {tag}", description="d", owner_id=people["other"]["user"])
    db.add_all([mine, untouched, theirs])
    db.flush()

    done = Concept(subject_id=mine.id, name="Done", description="first")
    todo = Concept(subject_id=mine.id, name="Todo", description="second")
    db.add_all([done, todo])
    db.flush()

    sid = people["me"]["student"]
    db.add(ConceptMastery(student_id=sid, concept_id=done.id, mastery_score=0.9, attempts=2, correct_answers=2))
    db.add(QuizQuestionRecord(
        student_id=sid, concept_id=done.id, question_text="What is X?",
        expected_answer="X is the thing.", difficulty="easy", answered=True,
    ))
    db.add(AssessmentAttempt(
        student_id=sid, concept_id=done.id, question="What is X?",
        student_answer="the thing", score=1.0, result="correct",
    ))
    db.add(Misconception(student_id=sid, concept_id=todo.id, description="Thinks Y is Z", resolved=False))
    db.commit()

    yield {**people, "mine": mine.id, "untouched": untouched.id, "theirs": theirs.id,
           "done": done.id, "todo": todo.id}

    db.rollback()
    ids = [mine.id, untouched.id, theirs.id]
    db.query(Misconception).filter(Misconception.student_id == sid).delete()
    db.query(AssessmentAttempt).filter(AssessmentAttempt.student_id == sid).delete()
    db.query(QuizQuestionRecord).filter(QuizQuestionRecord.student_id == sid).delete()
    db.query(ConceptMastery).filter(ConceptMastery.student_id == sid).delete()
    db.query(Concept).filter(Concept.subject_id.in_(ids)).delete(synchronize_session=False)
    db.query(Subject).filter(Subject.id.in_(ids)).delete(synchronize_session=False)
    for person in people.values():
        db.query(StudentProfile).filter_by(id=person["student"]).delete()
        db.query(User).filter_by(id=person["user"]).delete()
    db.commit()
    db.close()


def test_library_lists_own_and_started_courses_only(learner):
    response = client.get(
        f"/students/{learner['me']['student']}/library", headers=learner["me"]["headers"]
    )

    assert response.status_code == 200, response.text
    by_id = {course["subject_id"]: course for course in response.json()}

    assert learner["mine"] in by_id
    assert learner["untouched"] not in by_id  # shared and never started
    assert learner["theirs"] not in by_id  # someone else's private course

    course = by_id[learner["mine"]]
    assert course["is_private"] is True
    assert course["total_concepts"] == 2
    assert course["mastered_concepts"] == 1
    assert course["mastery"] == pytest.approx(0.45)
    assert course["last_activity"] is not None


def test_library_belongs_to_its_student(learner):
    response = client.get(
        f"/students/{learner['me']['student']}/library", headers=learner["other"]["headers"]
    )

    assert response.status_code in {403, 404}


def test_journal_shows_status_takeaways_and_misconceptions(learner):
    response = client.get(
        f"/students/{learner['me']['student']}/subjects/{learner['mine']}/journal",
        headers=learner["me"]["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mastered_concepts"] == 1

    done, todo = body["concepts"]
    assert done["status"] == "mastered"
    assert done["takeaways"] == ["X is the thing."]
    assert done["history"][0]["your_answer"] == "the thing"
    assert todo["status"] == "not_started"
    assert todo["open_misconceptions"] == ["Thinks Y is Z"]
    assert todo["takeaways"] == []


def test_journal_of_someone_elses_private_course_is_404(learner):
    response = client.get(
        f"/students/{learner['me']['student']}/subjects/{learner['theirs']}/journal",
        headers=learner["me"]["headers"],
    )

    assert response.status_code == 404
