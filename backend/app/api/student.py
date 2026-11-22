from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import (
    STAFF_ROLES,
    ensure_student_access,
    get_current_user,
    require_staff,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings

from app.models.curriculum import Concept, Subject
from app.db.database import SessionLocal
from app.models.student import (
    ConceptMastery,
    StudentProfile,
    User,
)
from app.schemas.student import (
    LearningLevelResponse,
    LearningLevelUpdate,
    MasteryResponse,
    MasteryUpdate,
    StudentBootstrapResponse,
    StudentProfileResponse,
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


def get_or_create_profile(db: Session, user: User) -> StudentProfile:
    """Return the user's learner profile, creating it on first use."""

    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user.id)
        .first()
    )

    if profile is None:
        profile = StudentProfile(
            user_id=user.id,
            learning_level="beginner",
        )
        db.add(profile)

        try:
            db.commit()

        except IntegrityError:
            # A simultaneous request created it first.
            db.rollback()
            profile = (
                db.query(StudentProfile)
                .filter(StudentProfile.user_id == user.id)
                .one()
            )

        else:
            db.refresh(profile)

    return profile


@router.get(
    "/me",
    response_model=StudentBootstrapResponse,
)
def get_my_student(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Identifiers the frontend needs for the signed-in user.

    The learner profile is created on first use, so staff accounts can
    also try the tutor.
    """

    profile = get_or_create_profile(db, current_user)

    return {
        "user_id": current_user.id,
        "student_id": profile.id,
        "username": current_user.username,
        "role": current_user.role,
        "learning_level": profile.learning_level,
    }


@router.patch(
    "/{student_id}/level",
    response_model=LearningLevelResponse,
)
def update_learning_level(
    student_id: int,
    update: LearningLevelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_student_access(
        db,
        current_user,
        student_id,
        allow_staff=False,
    )

    student = db.get(StudentProfile, student_id)

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    student.learning_level = update.learning_level

    db.commit()
    db.refresh(student)

    return {
        "student_id": student.id,
        "learning_level": student.learning_level,
    }


@router.post(
    "/{user_id}/profile",
    response_model=StudentProfileResponse,
    status_code=201,
)
def create_student_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to do that.",
        )

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
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id and current_user.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to do that.",
        )

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

    for mastery, _concept, subject in mastery_records:
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
            ConceptMastery.mastery_score
            < settings.prerequisite_mastery_threshold,
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
    _staff: User = Depends(require_staff),
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

    return (
        db.query(ConceptMastery)
        .filter(ConceptMastery.student_id == student_id)
        .all()
    )
