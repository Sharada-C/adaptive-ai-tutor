
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.student import User
from app.models.curriculum import Concept, Subject

from app.schemas.curriculum import (
    ConceptCreate,
    ConceptResponse,
    SubjectCreate,
    SubjectResponse,
)

from app.schemas.curriculum_generation import (
    CurriculumGenerateRequest,
    GeneratedCurriculum,
    SavedCurriculumResponse,
)

from app.services.curriculum_generator import generate_curriculum
from app.services.curriculum_persistence import save_generated_curriculum


router = APIRouter(
    prefix="/subjects",
    tags=["Curriculum"],
)


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=201,
)
def create_subject(
    subject: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can create subjects",
        )

    existing_subject = (
        db.query(Subject)
        .filter(Subject.name == subject.name)
        .first()
    )

    if existing_subject:
        raise HTTPException(
            status_code=409,
            detail="Subject already exists",
        )

    new_subject = Subject(
        name=subject.name,
        description=subject.description,
    )

    db.add(new_subject)
    db.commit()
    db.refresh(new_subject)

    return new_subject


@router.get(
    "",
    response_model=list[SubjectResponse],
)
def get_subjects(
    db: Session = Depends(get_db),
):
    return db.query(Subject).order_by(Subject.id).all()


@router.post(
    "/{subject_id}/concepts",
    response_model=ConceptResponse,
    status_code=201,
)
def create_concept(
    subject_id: int,
    concept: ConceptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can create concepts",
        )

    subject = db.get(Subject, subject_id)

    if not subject:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    new_concept = Concept(
        subject_id=subject_id,
        name=concept.name,
        description=concept.description,
    )

    db.add(new_concept)
    db.commit()
    db.refresh(new_concept)

    return new_concept


@router.get(
    "/{subject_id}/concepts",
    response_model=list[ConceptResponse],
)
def get_concepts(
    subject_id: int,
    db: Session = Depends(get_db),
):
    subject = db.get(Subject, subject_id)

    if not subject:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    return (
        db.query(Concept)
        .filter(Concept.subject_id == subject_id)
        .order_by(Concept.id)
        .all()
    )


@router.post(
    "/generate",
    response_model=SavedCurriculumResponse,
    status_code=201,
)
def generate_new_curriculum(
    request: CurriculumGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can generate curricula",
        )

    topic = request.topic.strip()

    if not topic:
        raise HTTPException(
            status_code=400,
            detail="Topic cannot be empty.",
        )

    try:
        curriculum_data = generate_curriculum(topic)

        curriculum = GeneratedCurriculum.model_validate(
            curriculum_data
        )

        subject = save_generated_curriculum(
            db=db,
            curriculum=curriculum,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return SavedCurriculumResponse(
        subject_id=subject.id,
        subject=subject.name,
        description=subject.description or "",
        concepts_created=len(subject.concepts),
    )
