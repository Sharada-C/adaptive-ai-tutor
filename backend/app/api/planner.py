from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.student import StudentProfile
from app.services.learning_planner import select_next_concept


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
):
    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
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