from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.student import StudentProfile, User
from app.services.learning_planner import select_next_concept


router = APIRouter(
    prefix="/students",
    tags=["Learning Planner"],
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



@router.get("/{student_id}/subjects/{subject_id}/next")
def get_next_concept(
    student_id: int,
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_accessible_student(
        student_id=student_id,
        current_user=current_user,
        db=db,
    )

    concept = select_next_concept(
        db=db,
        student_id=student_id,
        subject_id=subject_id,
    )

    if concept is None:
        return {
            "status": "complete",
            "message": "All available concepts are mastered.",
        }

    return {
        "status": "next",
        "concept": {
            "id": concept.id,
            "name": concept.name,
            "description": concept.description,
        },
    }