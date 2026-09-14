from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.student import (
    AssessmentAttempt,
    ConceptMastery,
    Misconception,
    StudentProfile,
)
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentResponse,
    MisconceptionCreate,
    MisconceptionResponse,
)


router = APIRouter(
    prefix="/students",
    tags=["Assessment"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/{student_id}/assessments",
    response_model=AssessmentResponse,
    status_code=201,
)
def record_assessment(
    student_id: int,
    assessment: AssessmentCreate,
    db: Session = Depends(get_db),
):
    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    attempt = AssessmentAttempt(
        student_id=student_id,
        concept_id=assessment.concept_id,
        question=assessment.question,
        student_answer=assessment.student_answer,
        score=assessment.score,
        result=assessment.result,
    )

    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return attempt


@router.post(
    "/{student_id}/misconceptions",
    response_model=MisconceptionResponse,
    status_code=201,
)
def record_misconception(
    student_id: int,
    misconception: MisconceptionCreate,
    db: Session = Depends(get_db),
):
    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    record = Misconception(
        student_id=student_id,
        concept_id=misconception.concept_id,
        description=misconception.description,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@router.get(
    "/{student_id}/misconceptions",
    response_model=list[MisconceptionResponse],
)
def get_misconceptions(
    student_id: int,
    db: Session = Depends(get_db),
):
    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    return (
        db.query(Misconception)
        .filter(Misconception.student_id == student_id)
        .order_by(Misconception.created_at.desc())
        .all()
    )


@router.get(
    "/{student_id}/assessments",
    response_model=list[AssessmentResponse],
)
def get_assessments(
    student_id: int,
    db: Session = Depends(get_db),
):
    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    return (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.student_id == student_id)
        .order_by(AssessmentAttempt.created_at.desc())
        .all()
    )