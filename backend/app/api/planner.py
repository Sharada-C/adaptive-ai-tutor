from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import ensure_student_access, get_current_user
from app.models.student import User
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.student import StudentProfile
from app.services.learning_planner import plan_next_concept


router = APIRouter(
    prefix="/students",
    tags=["Learning Planner"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get("/{student_id}/subjects/{subject_id}/next")
def get_next_concept(
    student_id: int,
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_student_access(
        db,
        current_user,
        student_id,
        allow_staff=True,
    )

    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    plan = plan_next_concept(
        db=db,
        student_id=student_id,
        subject_id=subject_id,
    )
    concept = plan.concept

    if concept is None:
        return {
            "status": plan.status,
            "message": plan.reason,
        }

    return {
        "status": "next",
        "message": plan.reason,
        "concept": {
            "id": concept.id,
            "name": concept.name,
            "description": concept.description,
        },
    }