"""Race-free updates to ``concept_mastery``."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.student import AssessmentAttempt, ConceptMastery


# A score is a recency-weighted average of the last attempts, pulled toward
# zero by this much "imaginary" evidence. One correct answer therefore gives
# 0.67 and two give 0.86, so a concept needs repeated success to reach the
# 0.80 advance threshold instead of being mastered after a single answer.
PRIOR_WEIGHT = 0.5


def lock_mastery(db: Session, student_id: int, concept_id: int) -> ConceptMastery:
    """Return the (student, concept) mastery row, locked until commit.

    ``INSERT .. ON CONFLICT DO NOTHING`` guarantees exactly one row even when
    requests race; ``SELECT .. FOR UPDATE`` makes concurrent requests for the
    same pair queue up so each sees the others' committed attempts.
    """

    db.execute(
        insert(ConceptMastery)
        .values(
            student_id=student_id,
            concept_id=concept_id,
            mastery_score=0.0,
            attempts=0,
            correct_answers=0,
        )
        .on_conflict_do_nothing(constraint="uq_student_concept_mastery")
    )

    return db.execute(
        select(ConceptMastery)
        .where(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == concept_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def refresh_mastery(db: Session, mastery: ConceptMastery) -> None:
    """Recompute counters and the recency-weighted score from the attempt log.

    Call after the new AssessmentAttempt has been added and flushed, while
    holding the lock from ``lock_mastery``.
    """

    db.flush()

    base = (
        AssessmentAttempt.student_id == mastery.student_id,
        AssessmentAttempt.concept_id == mastery.concept_id,
    )

    mastery.attempts = db.scalar(
        select(func.count(AssessmentAttempt.id)).where(*base)
    )
    mastery.correct_answers = db.scalar(
        select(func.count(AssessmentAttempt.id)).where(
            *base, AssessmentAttempt.result == "correct"
        )
    )

    recent = db.scalars(
        select(AssessmentAttempt)
        .where(*base)
        .order_by(AssessmentAttempt.created_at.desc(), AssessmentAttempt.id.desc())
        .limit(5)
    ).all()

    scores = [a.score for a in reversed(recent)]

    if scores:
        weights = range(1, len(scores) + 1)
        weighted = sum(s * w for s, w in zip(scores, weights, strict=True))
        score = weighted / (sum(weights) + PRIOR_WEIGHT)
        mastery.mastery_score = max(0.0, min(1.0, score))
