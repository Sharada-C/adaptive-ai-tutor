import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, or_

from app.api.deps import ensure_subject_access, get_current_user, require_staff
from app.core.config import settings
from app.models.student import User
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
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
)

from app.schemas.curriculum_generation import (
    MaterialSummary,
    SavedCurriculumResponse,
    TopicCourseRequest,
    TopicCourseResponse,
)
from app.rag.knowledge_ingestion import ingest_text_for_subject
from app.services.web_material import collect_material
from app.services.curriculum_generator import generate_curriculum
from app.services.curriculum_persistence import (
    save_generated_curriculum,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/subjects",
    tags=["Curriculum"],
)
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=201,
)
def create_subject(
    subject: SubjectCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_staff),
):
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
    user: User = Depends(get_current_user),
):
    """Shared courses plus the caller's own private ones."""

    return (
        db.query(Subject)
        .filter(or_(Subject.owner_id.is_(None), Subject.owner_id == user.id))
        .order_by(Subject.id)
        .all()
    )


@router.post(
    "/{subject_id}/concepts",
    response_model=ConceptResponse,
    status_code=201,
)
def create_concept(
    subject_id: int,
    concept: ConceptCreate,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_staff),
):
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
    user: User = Depends(get_current_user),
):
    ensure_subject_access(db, user, subject_id)

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
    _staff: User = Depends(require_staff),
):
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
        ) from error

    return SavedCurriculumResponse(
        subject_id=subject.id,
        subject=subject.name,
        description=subject.description or "",
        concepts_created=len(subject.concepts),
    )


def _attach_wikipedia_material(db: Session, subject: Subject) -> MaterialSummary:
    """Best effort: a failure here must never lose the course."""

    articles: list[str] = []
    chunks = 0

    for article in collect_material(
        subject.name, [concept.name for concept in subject.concepts]
    ):
        try:
            inserted = ingest_text_for_subject(
                db=db,
                subject_id=subject.id,
                text=article.text,
                source=article.source,
            )
        except Exception as error:
            db.rollback()
            logger.warning("Could not store %s: %s", article.title, error)
            continue

        if inserted:
            articles.append(article.title)
            chunks += inserted

    return MaterialSummary(articles=articles, chunks=chunks)


def _topic_response(
    subject: Subject,
    created: bool,
    material: MaterialSummary,
) -> TopicCourseResponse:
    needs_material = material.chunks == 0

    if not created:
        message = "You already have a course on this topic."
        needs_material = False
    elif needs_material:
        message = (
            "Your course is ready, but no study material could be found "
            "automatically. Upload your own notes or a PDF to ground the tutor."
        )
    else:
        message = (
            f"Your course is ready with {len(material.articles)} Wikipedia "
            "article(s) as study material. You can also upload your own notes."
        )

    return TopicCourseResponse(
        subject_id=subject.id,
        subject=subject.name,
        description=subject.description or "",
        concepts_created=len(subject.concepts),
        created=created,
        material=material,
        needs_material=needs_material,
        message=message,
    )


@router.post("/from-topic", response_model=TopicCourseResponse, status_code=201)
def create_course_from_topic(
    request: TopicCourseRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Any signed-in user can learn any topic.

    Generates a concept path with the LLM, saves it as a course that only
    this user can see, and attaches cited Wikipedia text as study material.
    """

    topic = request.topic

    existing = (
        db.query(Subject)
        .filter(
            Subject.owner_id == user.id,
            func.lower(Subject.name) == topic.lower(),
        )
        .first()
    )

    if existing:
        response.status_code = 200
        return _topic_response(
            existing, created=False, material=MaterialSummary(articles=[], chunks=0)
        )

    owned = db.query(Subject).filter(Subject.owner_id == user.id).count()

    if owned >= settings.max_courses_per_user:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Course limit reached ({settings.max_courses_per_user}). "
                "Remove a course before adding another."
            ),
        )

    try:
        curriculum = GeneratedCurriculum.model_validate(generate_curriculum(topic))
        # Keep the course named exactly as the student asked.
        curriculum.subject = topic
        subject = save_generated_curriculum(
            db=db, curriculum=curriculum, owner_id=user.id
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    material = _attach_wikipedia_material(db, subject)
    db.refresh(subject)

    return _topic_response(subject, created=True, material=material)
