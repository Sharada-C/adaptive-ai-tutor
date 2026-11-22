"""Prerequisite lookups shared by the planner and the tutor endpoints."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.curriculum import Concept
from app.models.student import ConceptMastery


def _mastery(db: Session, student_id: int, concept_id: int) -> float:
    row = (
        db.query(ConceptMastery)
        .filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == concept_id,
        )
        .first()
    )
    return row.mastery_score if row else 0.0


def blocking_prerequisite(
    db: Session, student_id: int, concept: Concept
) -> dict | None:
    """The weakest prerequisite below the mastery threshold, or None."""

    weakest = None

    for prerequisite in concept.prerequisites:
        score = _mastery(db, student_id, prerequisite.id)

        if score < settings.prerequisite_mastery_threshold and (
            weakest is None or score < weakest["mastery_score"]
        ):
            weakest = {
                "concept_id": prerequisite.id,
                "concept": prerequisite.name,
                "mastery_score": score,
            }

    return weakest


def locked_concept_detail(
    db: Session, student_id: int, concept_id: int
) -> dict | None:
    """Body for a 409 when a student asks for a concept that is still locked."""

    concept = db.get(Concept, concept_id)

    if concept is None:
        return None

    blocker = blocking_prerequisite(db, student_id, concept)

    if blocker is None:
        return None

    return {
        "code": "prerequisite_required",
        "message": (
            f"'{concept.name}' is locked until you master "
            f"'{blocker['concept']}'."
        ),
        "prerequisite_concept_id": blocker["concept_id"],
        "prerequisite_concept": blocker["concept"],
        "prerequisite_mastery_score": blocker["mastery_score"],
        "threshold": settings.prerequisite_mastery_threshold,
    }
