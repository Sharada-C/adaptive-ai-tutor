from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_user
from app.models.student import (
    AssessmentAttempt,
    Misconception,
    StudentProfile,
    User,
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
@router.post(
    "/{student_id}/assessments",
    response_model=AssessmentResponse,
    status_code=201,
)
def record_assessment(
    student_id: int,
    assessment: AssessmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = get_accessible_student(
        student_id=student_id,
        current_user=current_user,
        db=db,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = get_accessible_student(
        student_id=student_id,
        current_user=current_user,
        db=db,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = get_accessible_student(
        student_id=student_id,
        current_user=current_user,
        db=db,
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = get_accessible_student(
        student_id=student_id,
        current_user=current_user,
        db=db,
    )
    return (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.student_id == student_id)
        .order_by(AssessmentAttempt.created_at.desc())
        .all()
    )
