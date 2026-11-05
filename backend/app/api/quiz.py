from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.student import StudentProfile, User
from app.schemas.quiz import QuizQuestion, QuizRequest
from app.tutor.context_builder import build_tutor_context
from app.tutor.quiz_service import generate_quiz
from app.rag.retriever import retrieve_relevant_chunks


router = APIRouter(
    prefix="/tutor",
    tags=["Quiz"],
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
    "/quiz",
    response_model=QuizQuestion,
)
def create_quiz(
    request: QuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_accessible_student(
        student_id=request.student_id,
        current_user=current_user,
        db=db,
    )
    try:
        context = build_tutor_context(
            db=db,
            student_id=request.student_id,
            concept_id=request.concept_id,
        )

    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Quiz context could not be created.",
        )

    # ---------------------------------------------------------
    # Retrieve concept-specific knowledge using pgvector
    # ---------------------------------------------------------
    knowledge_chunks = retrieve_relevant_chunks(
        db=db,
        query=context["concept"],
        concept_id=request.concept_id,
        limit=3,
    )

    knowledge_text = "\n\n".join(
        f"[Knowledge {index}]\n{chunk.content}"
        for index, chunk in enumerate(
            knowledge_chunks,
            start=1,
        )
    )

    if not knowledge_text:
        knowledge_text = "No retrieved knowledge available."

    # ---------------------------------------------------------
    # Generate grounded adaptive quiz
    # ---------------------------------------------------------
    return generate_quiz(
        concept=context["concept"],
        concept_description=context["concept_description"],
        student_level=context["student_level"],
        mastery_score=context["mastery_score"],
        knowledge_text=knowledge_text,
        misconceptions=context["misconceptions"],
    )