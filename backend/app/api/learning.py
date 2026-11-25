"""A learner's library of courses and a journal of what they have learned."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import (
    ensure_student_access,
    ensure_subject_access,
    get_current_user,
)
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.curriculum import Subject
from app.models.student import (
    AssessmentAttempt,
    ConceptMastery,
    DiagnosticQuestion,
    DiagnosticSession,
    Misconception,
    QuizQuestionRecord,
    User,
)

router = APIRouter(prefix="/students", tags=["Learning"])

MAX_TAKEAWAYS = 3
MAX_HISTORY = 6
TAKEAWAY_CHARS = 320


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


class LibraryCourse(BaseModel):
    subject_id: int
    name: str
    is_private: bool
    total_concepts: int
    mastered_concepts: int
    mastery: float
    last_activity: datetime | None


class HistoryItem(BaseModel):
    question: str
    your_answer: str
    score: float
    result: str
    when: datetime | None


class JournalConcept(BaseModel):
    concept_id: int
    name: str
    description: str | None
    status: str  # mastered | learning | not_started
    mastery: float
    attempts: int
    correct_answers: int
    last_studied: datetime | None
    takeaways: list[str]
    open_misconceptions: list[str]
    history: list[HistoryItem]


class Journal(BaseModel):
    subject_id: int
    name: str
    is_private: bool
    total_concepts: int
    mastered_concepts: int
    mastery: float
    concepts: list[JournalConcept]


def _is_mastered(score: float) -> bool:
    return score >= settings.prerequisite_mastery_threshold


def _clip(text: str) -> str:
    text = " ".join(text.split())

    return text if len(text) <= TAKEAWAY_CHARS else text[: TAKEAWAY_CHARS - 1] + "…"


@router.get("/{student_id}/library", response_model=list[LibraryCourse])
def get_library(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Courses the learner created or has started, most recent first."""

    ensure_student_access(db, current_user, student_id, allow_staff=False)

    subjects = (
        db.query(Subject)
        .filter(or_(Subject.owner_id.is_(None), Subject.owner_id == current_user.id))
        .order_by(Subject.name)
        .all()
    )

    mastery_rows = {
        row.concept_id: row
        for row in db.query(ConceptMastery).filter(ConceptMastery.student_id == student_id)
    }

    last_by_concept: dict[int, datetime] = {}

    for concept_id, created in (
        db.query(AssessmentAttempt.concept_id, AssessmentAttempt.created_at)
        .filter(AssessmentAttempt.student_id == student_id)
        .all()
    ):
        if concept_id not in last_by_concept or created > last_by_concept[concept_id]:
            last_by_concept[concept_id] = created

    library: list[LibraryCourse] = []

    for subject in subjects:
        concept_ids = [concept.id for concept in subject.concepts]
        started = any(
            cid in mastery_rows and mastery_rows[cid].attempts > 0
            for cid in concept_ids
        )

        if not started and subject.owner_id != current_user.id:
            continue

        scores = [
            mastery_rows[cid].mastery_score if cid in mastery_rows else 0.0
            for cid in concept_ids
        ]
        dates = [last_by_concept[cid] for cid in concept_ids if cid in last_by_concept]

        library.append(
            LibraryCourse(
                subject_id=subject.id,
                name=subject.name,
                is_private=subject.owner_id is not None,
                total_concepts=len(concept_ids),
                mastered_concepts=sum(1 for score in scores if _is_mastered(score)),
                mastery=sum(scores) / len(scores) if scores else 0.0,
                last_activity=max(dates) if dates else None,
            )
        )

    library.sort(
        key=lambda c: (c.last_activity is None, -(c.last_activity.timestamp() if c.last_activity else 0)),
    )

    return library


@router.get("/{student_id}/subjects/{subject_id}/journal", response_model=Journal)
def get_journal(
    student_id: int,
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per concept: status, key takeaways from questions answered well, open
    misconceptions and the most recent answers."""

    ensure_student_access(db, current_user, student_id, allow_staff=False)
    subject = ensure_subject_access(db, current_user, subject_id)

    concepts = sorted(subject.concepts, key=lambda c: c.id)
    concept_ids = [concept.id for concept in concepts]

    mastery_rows = {
        row.concept_id: row
        for row in db.query(ConceptMastery).filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id.in_(concept_ids),
        )
    }

    expected = {
        (row.concept_id, row.question_text.strip()): row.expected_answer
        for row in db.query(QuizQuestionRecord).filter(
            QuizQuestionRecord.student_id == student_id,
            QuizQuestionRecord.concept_id.in_(concept_ids),
        )
    }

    # Every answer the learner gave, from quizzes and from the diagnostic.
    answers: dict[int, list[dict]] = {cid: [] for cid in concept_ids}

    for attempt in db.query(AssessmentAttempt).filter(
        AssessmentAttempt.student_id == student_id,
        AssessmentAttempt.concept_id.in_(concept_ids),
    ):
        answers[attempt.concept_id].append(
            {
                "question": attempt.question,
                "answer": attempt.student_answer,
                "score": attempt.score,
                "result": attempt.result,
                "when": attempt.created_at,
                "model": expected.get((attempt.concept_id, attempt.question.strip())),
            }
        )

    diagnostic_rows = (
        db.query(DiagnosticQuestion)
        .join(DiagnosticSession, DiagnosticSession.id == DiagnosticQuestion.session_id)
        .filter(
            DiagnosticSession.student_id == student_id,
            DiagnosticQuestion.concept_id.in_(concept_ids),
            DiagnosticQuestion.answered.is_(True),
        )
        .all()
    )

    for row in diagnostic_rows:
        answers[row.concept_id].append(
            {
                "question": row.question,
                "answer": row.student_answer or "",
                "score": row.score or 0.0,
                "result": row.result or "",
                "when": row.created_at,
                "model": row.expected_answer,
            }
        )

    misconceptions: dict[int, list[str]] = {cid: [] for cid in concept_ids}

    for item in db.query(Misconception).filter(
        Misconception.student_id == student_id,
        Misconception.concept_id.in_(concept_ids),
        Misconception.resolved.is_(False),
    ):
        if item.description not in misconceptions[item.concept_id]:
            misconceptions[item.concept_id].append(item.description)

    journal: list[JournalConcept] = []

    for concept in concepts:
        row = mastery_rows.get(concept.id)
        score = row.mastery_score if row else 0.0
        attempts = row.attempts if row else 0
        given = sorted(
            answers[concept.id],
            key=lambda a: a["when"] or datetime.min,
            reverse=True,
        )

        takeaways: list[str] = []

        for item in given:
            if item["score"] >= 0.8 and item["model"]:
                text = _clip(item["model"])

                if text not in takeaways:
                    takeaways.append(text)

            if len(takeaways) >= MAX_TAKEAWAYS:
                break

        status = (
            "mastered"
            if _is_mastered(score)
            else "learning"
            if attempts > 0
            else "not_started"
        )

        journal.append(
            JournalConcept(
                concept_id=concept.id,
                name=concept.name,
                description=concept.description,
                status=status,
                mastery=score,
                attempts=attempts,
                correct_answers=row.correct_answers if row else 0,
                last_studied=given[0]["when"] if given else None,
                takeaways=takeaways,
                open_misconceptions=misconceptions[concept.id],
                history=[
                    HistoryItem(
                        question=item["question"],
                        your_answer=item["answer"],
                        score=item["score"],
                        result=item["result"],
                        when=item["when"],
                    )
                    for item in given[:MAX_HISTORY]
                ],
            )
        )

    scores = [item.mastery for item in journal]

    return Journal(
        subject_id=subject.id,
        name=subject.name,
        is_private=subject.owner_id is not None,
        total_concepts=len(journal),
        mastered_concepts=sum(1 for item in journal if item.status == "mastered"),
        mastery=sum(scores) / len(scores) if scores else 0.0,
        concepts=journal,
    )
