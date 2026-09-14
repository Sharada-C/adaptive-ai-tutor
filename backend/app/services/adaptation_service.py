from sqlalchemy.orm import Session

from app.models.student import ConceptMastery, Misconception
from app.models.curriculum import Concept
from app.services.adaptive_engine import decide_next_action


PREREQUISITE_THRESHOLD = 0.70


def get_concept_mastery(
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


def check_prerequisites_mastered(
    db: Session,
    student_id: int,
    concept_id: int,
) -> bool:

    concept = db.get(Concept, concept_id)

    if not concept:
        return False

    prerequisites = concept.prerequisites

    # No prerequisites means the concept is ready.
    if not prerequisites:
        return True

    for prerequisite in prerequisites:

        prerequisite_mastery = get_concept_mastery(
            db=db,
            student_id=student_id,
            concept_id=prerequisite.id,
        )

        if prerequisite_mastery < PREREQUISITE_THRESHOLD:
            return False

    return True


def determine_student_action(
    db: Session,
    student_id: int,
    concept_id: int,
):
    # ---------------------------------------------------------
    # 1. Get current concept mastery
    # ---------------------------------------------------------
    mastery_score = get_concept_mastery(
        db=db,
        student_id=student_id,
        concept_id=concept_id,
    )

    # ---------------------------------------------------------
    # 2. Check active misconceptions
    # ---------------------------------------------------------
    active_misconception = (
        db.query(Misconception)
        .filter(
            Misconception.student_id == student_id,
            Misconception.concept_id == concept_id,
            Misconception.resolved.is_(False),
        )
        .first()
    )

    has_active_misconception = (
        active_misconception is not None
    )

    # ---------------------------------------------------------
    # 3. Check prerequisites
    # ---------------------------------------------------------
    prerequisites_mastered = check_prerequisites_mastered(
        db=db,
        student_id=student_id,
        concept_id=concept_id,
    )

    # ---------------------------------------------------------
    # 4. Find weakest prerequisite
    # ---------------------------------------------------------
    weakest_prerequisite = None

    if not prerequisites_mastered:
        weakest_prerequisite = get_weakest_prerequisite(
            db=db,
            student_id=student_id,
            concept_id=concept_id,
        )

    # ---------------------------------------------------------
    # 5. Make adaptive decision
    # ---------------------------------------------------------
    return decide_next_action(
        mastery_score=mastery_score,
        has_active_misconception=has_active_misconception,
        prerequisites_mastered=prerequisites_mastered,
        weakest_prerequisite=weakest_prerequisite,
    )
def get_weakest_prerequisite(
    db: Session,
    student_id: int,
    concept_id: int,
):
    concept = db.get(Concept, concept_id)

    if not concept:
        return None

    prerequisites = concept.prerequisites

    if not prerequisites:
        return None

    weakest = None
    weakest_score = float("inf")

    for prerequisite in prerequisites:
        score = get_concept_mastery(
            db=db,
            student_id=student_id,
            concept_id=prerequisite.id,
        )

        if score < weakest_score:
            weakest_score = score
            weakest = prerequisite

    if weakest is None:
        return None

    return {
        "concept_id": weakest.id,
        "concept": weakest.name,
        "mastery_score": weakest_score,
    }