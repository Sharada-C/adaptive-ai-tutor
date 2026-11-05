from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_user
from app.models.student import StudentProfile, User
from app.models.curriculum import Concept
from app.services.adaptation_service import determine_student_action
from app.schemas.next_action import NextActionResponse


router = APIRouter(
    prefix="/tutor",
    tags=["Adaptive Tutor"],
)
def get_accessible_student(
    student_id: int,
    current_user: User,
    db: Session,
) -> StudentProfile:

    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    if current_user.role != "admin" and student.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this student's data",
        )

    return student


@router.get(
    "/next/{student_id}/{concept_id}",
    response_model=NextActionResponse,
)
def get_next_action(
    student_id: int,
    concept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Validate student ownership
    student = get_accessible_student(
        student_id=student_id,
        current_user=current_user,
        db=db,
    )

    # 2. Validate concept
    concept = db.get(Concept, concept_id)

    if not concept:
        raise HTTPException(
            status_code=404,
            detail="Concept not found.",
        )

    # 3. Determine adaptive action
    decision = determine_student_action(
        db=db,
        student_id=student.id,
        concept_id=concept_id,
    )

    # 4. Return actionable decision
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