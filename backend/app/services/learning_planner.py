from sqlalchemy.orm import Session

from app.models.curriculum import Concept
from app.models.student import ConceptMastery


MASTERY_THRESHOLD = 0.80


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
    for prerequisite in concept.prerequisites:
        mastery = get_mastery(
            db,
            student_id,
            prerequisite.id,
        )

        if mastery < MASTERY_THRESHOLD:
            return False

    return True


def select_next_concept(
    db: Session,
    student_id: int,
    subject_id: int,
) -> Concept | None:

    concepts = (
        db.query(Concept)
        .filter(Concept.subject_id == subject_id)
        .order_by(Concept.id)
        .all()
    )

    for concept in concepts:

        mastery = get_mastery(
            db,
            student_id,
            concept.id,
        )

        # Already mastered.
        if mastery >= MASTERY_THRESHOLD:
            continue

        # Don't introduce a concept until
        # its prerequisites are understood.
        if not prerequisites_satisfied(
            db,
            student_id,
            concept,
        ):
            continue

        return concept

    return None