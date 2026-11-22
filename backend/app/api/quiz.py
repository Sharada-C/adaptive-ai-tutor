from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import ensure_student_access, get_current_user
from app.models.student import User
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.curriculum import Concept
from app.models.student import QuizQuestionRecord
from app.schemas.quiz import QuizQuestion, QuizRequest
from app.tutor.context_builder import build_tutor_context
from app.tutor.quiz_service import generate_quiz
from app.services.prerequisite_service import locked_concept_detail
from app.rag.retriever import retrieve_with_subject_fallback


router = APIRouter(
    prefix="/tutor",
    tags=["Quiz"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/quiz",
    response_model=QuizQuestion,
)
def create_quiz(
    request: QuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_student_access(
        db,
        current_user,
        request.student_id,
        allow_staff=False,
    )

    locked = locked_concept_detail(db, request.student_id, request.concept_id)

    if locked:
        raise HTTPException(status_code=409, detail=locked)

    try:
        context = build_tutor_context(
            db=db,
            student_id=request.student_id,
            concept_id=request.concept_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    concept = db.get(Concept, request.concept_id)

    # ---------------------------------------------------------
    # Retrieve knowledge using pgvector. Concept-specific chunks
    # are preferred; subject-wide material is used as a fallback
    # so that a single uploaded document can ground the quiz.
    # ---------------------------------------------------------
    knowledge_chunks = retrieve_with_subject_fallback(
        db=db,
        query=context["concept"],
        concept_id=request.concept_id,
        subject_id=concept.subject_id if concept else None,
        limit=3,
    )

    knowledge_text = "\n\n".join(
        f"[Knowledge {index}]\n{item['chunk'].content}"
        for index, item in enumerate(
            knowledge_chunks,
            start=1,
        )
    )

    if not knowledge_text:
        knowledge_text = "No retrieved knowledge available."

    # ---------------------------------------------------------
    # Generate grounded adaptive quiz
    # ---------------------------------------------------------
    try:
        generated = generate_quiz(
            concept=context["concept"],
            concept_description=context["concept_description"],
            student_level=context["student_level"],
            mastery_score=context["mastery_score"],
            knowledge_text=knowledge_text,
            misconceptions=context["misconceptions"],
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=(
                "A grounded quiz question could not be generated "
                f"for this concept: {error}"
            ),
        ) from error

    # Persist the expected answer server-side; the client only gets an id.
    record = QuizQuestionRecord(
        student_id=request.student_id,
        concept_id=request.concept_id,
        question_text=generated["question"],
        expected_answer=generated["expected_answer"],
        difficulty=generated.get("difficulty"),
    )
    db.add(record)
    db.commit()

    return QuizQuestion(
        question_id=record.id,
        question=record.question_text,
        difficulty=record.difficulty or "medium",
    )
