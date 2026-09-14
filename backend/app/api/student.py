from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.student import (
    ConceptMastery,
    StudentProfile,
    User,
)
from app.schemas.student import (
    MasteryResponse,
    MasteryUpdate,
    StudentProfileResponse,
    UserCreate,
    UserResponse,
)


router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.username == user.username)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    new_user = User(
        username=user.username,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post(
    "/{user_id}/profile",
    response_model=StudentProfileResponse,
    status_code=201,
)
def create_student_profile(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    existing_profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .first()
    )

    if existing_profile:
        raise HTTPException(
            status_code=409,
            detail="Student profile already exists",
        )

    profile = StudentProfile(
        user_id=user_id,
        learning_level="beginner",
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


@router.post(
    "/{student_id}/mastery",
    response_model=MasteryResponse,
)
def update_mastery(
    student_id: int,
    mastery: MasteryUpdate,
    db: Session = Depends(get_db),
):
    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    existing = (
        db.query(ConceptMastery)
        .filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == mastery.concept_id,
        )
        .first()
    )

    if existing:
        existing.mastery_score = mastery.mastery_score
        existing.attempts = mastery.attempts
        existing.correct_answers = mastery.correct_answers

        db.commit()
        db.refresh(existing)

        return existing

    record = ConceptMastery(
        student_id=student_id,
        concept_id=mastery.concept_id,
        mastery_score=mastery.mastery_score,
        attempts=mastery.attempts,
        correct_answers=mastery.correct_answers,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@router.get(
    "/{student_id}/mastery",
    response_model=list[MasteryResponse],
)
def get_mastery(
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
        db.query(ConceptMastery)
        .filter(ConceptMastery.student_id == student_id)
        .all()
    )