from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.curriculum import Concept, Subject
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

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "learning_level": profile.learning_level,
        "overall_mastery": 0.0,
        "subject_mastery": [],
        "concepts_to_strengthen": [],
    }


@router.get(
    "/{user_id}/profile",
    response_model=StudentProfileResponse,
)
def get_student_profile(
    user_id: int,
    db: Session = Depends(get_db),
):
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    mastery_records = (
        db.query(ConceptMastery, Concept, Subject)
        .join(
            Concept,
            ConceptMastery.concept_id == Concept.id,
        )
        .join(
            Subject,
            Concept.subject_id == Subject.id,
        )
        .filter(
            ConceptMastery.student_id == profile.id,
        )
        .all()
    )

    if mastery_records:
        overall_mastery = (
            sum(
                mastery.mastery_score
                for mastery, concept, subject in mastery_records
            )
            / len(mastery_records)
        )
    else:
        overall_mastery = 0.0

    subject_groups = {}

    for mastery, concept, subject in mastery_records:
        if subject.id not in subject_groups:
            subject_groups[subject.id] = {
                "subject_id": subject.id,
                "subject_name": subject.name,
                "scores": [],
            }

        subject_groups[subject.id]["scores"].append(
            mastery.mastery_score
        )

    subject_mastery = []

    for data in subject_groups.values():
        mastery = (
            sum(data["scores"]) / len(data["scores"])
            if data["scores"]
            else 0.0
        )

        subject_mastery.append(
            {
                "subject_id": data["subject_id"],
                "subject_name": data["subject_name"],
                "mastery": mastery,
            }
        )

    concepts_to_strengthen = (
        db.query(
            ConceptMastery,
            Concept,
            Subject,
        )
        .join(
            Concept,
            ConceptMastery.concept_id == Concept.id,
        )
        .join(
            Subject,
            Concept.subject_id == Subject.id,
        )
        .filter(
            ConceptMastery.student_id == profile.id,
            ConceptMastery.mastery_score < 0.80,
        )
        .order_by(
            ConceptMastery.mastery_score.asc()
        )
        .limit(5)
        .all()
    )

    concepts_to_strengthen_response = [
        {
            "concept_id": mastery.concept_id,
            "concept_name": concept.name,
            "subject_name": subject.name,
            "mastery": mastery.mastery_score,
        }
        for mastery, concept, subject in concepts_to_strengthen
    ]

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "learning_level": profile.learning_level,
        "overall_mastery": overall_mastery,
        "subject_mastery": subject_mastery,
        "concepts_to_strengthen": concepts_to_strengthen_response,
    }


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
