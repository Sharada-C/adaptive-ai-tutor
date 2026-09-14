from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.curriculum import Concept
from app.models.student import StudentProfile
from app.services.adaptation_service import determine_student_action
from app.schemas.next_action import NextActionResponse


router = APIRouter(
    prefix="/tutor",
    tags=["Adaptive Tutor"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get(
    "/next/{student_id}/{concept_id}",
    response_model=NextActionResponse,
)
def get_next_action(
    student_id: int,
    concept_id: int,
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------------
    # 1. Validate student
    # ---------------------------------------------------------

    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found.",
        )

    # ---------------------------------------------------------
    # 2. Validate concept
    # ---------------------------------------------------------

    concept = db.get(Concept, concept_id)

    if not concept:
        raise HTTPException(
            status_code=404,
            detail="Concept not found.",
        )

    # ---------------------------------------------------------
    # 3. Determine adaptive action
    # ---------------------------------------------------------

    decision = determine_student_action(
        db=db,
        student_id=student_id,
        concept_id=concept_id,
    )

    # ---------------------------------------------------------
    # 4. Return actionable decision
    # ---------------------------------------------------------

    return NextActionResponse(
        action=decision.action,
        reason=decision.reason,
        concept_id=concept.id,
        concept=concept.name,
        mastery_score=decision.mastery_score,
        prerequisite_concept_id=decision.prerequisite_concept_id,
        prerequisite_concept=decision.prerequisite_concept,
        prerequisite_mastery_score=decision.prerequisite_mastery_score,
    )