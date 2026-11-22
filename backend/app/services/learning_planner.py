from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.curriculum import Concept
from app.models.student import ConceptMastery
from app.services.prerequisite_service import blocking_prerequisite


MASTERY_THRESHOLD = settings.prerequisite_mastery_threshold


@dataclass
class PlanDecision:
    """What to study next, or an explicit reason there is nothing to study."""

    status: str  # "next" | "complete" | "blocked"
    reason: str
    concept: Concept | None = None


def get_mastery(
    db: Session,
    student_id: int,
    concept_id: int,
) -> float:
    mastery = (
        db.query(ConceptMastery)
        .filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == concept_id,
        )
        .first()
    )

    if not mastery:
        return 0.0

    return mastery.mastery_score


def prerequisites_satisfied(
    db: Session,
    student_id: int,
    concept: Concept,
) -> bool:
    return blocking_prerequisite(db, student_id, concept) is None


def _deepest_blocker(db: Session, student_id: int, concept: Concept) -> Concept:
    """Follow weakest-unmastered prerequisites down to one that can be studied."""

    seen = {concept.id}
    current = concept

    while True:
        blocker = blocking_prerequisite(db, student_id, current)

        if blocker is None:
            return current

        nxt = next(p for p in current.prerequisites if p.id == blocker["concept_id"])

        if nxt.id in seen:  # circular data: stop rather than loop forever
            return current

        seen.add(nxt.id)
        current = nxt


def plan_next_concept(
    db: Session,
    student_id: int,
    subject_id: int,
) -> PlanDecision:
    concepts = (
        db.query(Concept)
        .filter(Concept.subject_id == subject_id)
        .order_by(Concept.id)
        .all()
    )

    if not concepts:
        return PlanDecision("complete", "This subject has no concepts yet.")

    unmastered_locked = 0

    for concept in concepts:
        mastered = get_mastery(db, student_id, concept.id) >= MASTERY_THRESHOLD
        satisfied = prerequisites_satisfied(db, student_id, concept)

        if mastered and satisfied:
            continue

        if satisfied:
            return PlanDecision(
                "next", "Next concept to learn.", concept
            )

        if mastered:
            # Mastered, but a prerequisite slipped: revisit that instead.
            target = _deepest_blocker(db, student_id, concept)

            if target.id != concept.id:
                return PlanDecision(
                    "next",
                    f"Revisit '{target.name}' before continuing with "
                    f"'{concept.name}'.",
                    target,
                )

        unmastered_locked += 1

    if unmastered_locked:
        return PlanDecision(
            "blocked",
            f"{unmastered_locked} concept(s) are locked behind prerequisites "
            "that can never be satisfied (the prerequisite graph may contain "
            "a cycle). Ask an instructor to fix the curriculum.",
        )

    return PlanDecision("complete", "All available concepts are mastered.")


def select_next_concept(
    db: Session,
    student_id: int,
    subject_id: int,
) -> Concept | None:
    """Compatibility wrapper: the concept to study, or None."""

    return plan_next_concept(db, student_id, subject_id).concept
