import json

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import (
    ensure_student_access,
    ensure_subject_access,
    get_current_user,
)
from app.services.mastery_service import lock_mastery, refresh_mastery
from app.models.student import User
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.curriculum import Subject, Concept
from app.models.student import (
    StudentProfile,
    AssessmentAttempt,
    Misconception,
    DiagnosticSession,
    DiagnosticQuestion,
)

from app.schemas.diagnostic import (
    DiagnosticStartRequest,
    DiagnosticStartResponse,
    DiagnosticSubmitRequest,
    DiagnosticSubmitResponse,
)

from app.tutor.evaluation_service import evaluate_answer
from app.tutor.diagnostic_service import generate_diagnostic


router = APIRouter(
    prefix="/tutor/diagnostic",
    tags=["Diagnostic Assessment"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/start",
    response_model=DiagnosticStartResponse,
)
def start_diagnostic(
    request: DiagnosticStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_student_access(
        db,
        current_user,
        request.student_id,
        allow_staff=False,
    )

    ensure_subject_access(db, current_user, request.subject_id)

    student = db.get(
        StudentProfile,
        request.student_id,
    )

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    subject = db.get(
        Subject,
        request.subject_id,
    )

    if not subject:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    try:
        diagnostic = generate_diagnostic(
            db=db,
            student_id=request.student_id,
            subject_id=request.subject_id,
            student_level=student.learning_level,
            limit=request.limit,
        )

    except ValueError as error:
        # Raised when no study material exists for a concept or the
        # model returns unusable content. Report it instead of a 500.
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    if not diagnostic:
        raise HTTPException(
            status_code=400,
            detail="No diagnostic questions could be generated.",
        )

    # Create a persistent diagnostic session
    session = DiagnosticSession(
        student_id=request.student_id,
        subject_id=request.subject_id,
        status="in_progress",
    )

    db.add(session)
    db.flush()

    # Store every generated question and its trusted
    # evaluation information on the server.
    for item in diagnostic:

        evaluation_criteria = item.get(
            "evaluation_criteria",
            [],
        )

        question = DiagnosticQuestion(
            session_id=session.id,
            concept_id=item["concept_id"],
            question=item["question"],
            expected_answer=item["expected_answer"],
            evaluation_criteria=json.dumps(
                evaluation_criteria
            ),
            misconception_guidance=item.get(
                "misconception_guidance",
                "",
            ),
        )

        db.add(question)

    db.commit()

    # Refresh so the session ID is guaranteed to exist.
    db.refresh(session)

    # Do NOT expose expected_answer,
    # evaluation_criteria, or misconception_guidance
    # to the client.
    questions = []

    stored_questions = (
        db.query(DiagnosticQuestion)
        .filter(
            DiagnosticQuestion.session_id == session.id
        )
        .order_by(DiagnosticQuestion.id)
        .all()
    )

    for question in stored_questions:

        concept = db.get(
            Concept,
            question.concept_id,
        )

        questions.append(
            {
                "question_id": question.id,
                "concept_id": question.concept_id,
                "concept": concept.name if concept else None,
                "question": question.question,
            }
        )

    return {
        "student_id": request.student_id,
        "subject_id": request.subject_id,
        "subject": subject.name,
        "session_id": session.id,
        "questions": questions,
    }


@router.post(
    "/submit",
    response_model=DiagnosticSubmitResponse,
)
def submit_diagnostic_answer(
    request: DiagnosticSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_student_access(
        db,
        current_user,
        request.student_id,
        allow_staff=False,
    )

    student = db.get(
        StudentProfile,
        request.student_id,
    )

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found.",
        )

    # Retrieve the stored diagnostic question.
    question = db.get(
        DiagnosticQuestion,
        request.question_id,
    )

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Diagnostic question not found.",
        )

    # Security check:
    # the question must belong to this student's session.
    session = db.get(
        DiagnosticSession,
        question.session_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Diagnostic session not found.",
        )

    if session.student_id != request.student_id:
        raise HTTPException(
            status_code=403,
            detail="This diagnostic question does not belong to the student.",
        )

    if session.status != "in_progress":
        raise HTTPException(
            status_code=400,
            detail="Diagnostic session is no longer active.",
        )

    if question.answered:
        raise HTTPException(
            status_code=400,
            detail="This diagnostic question has already been answered.",
        )

    concept = db.get(
        Concept,
        question.concept_id,
    )

    if not concept:
        raise HTTPException(
            status_code=404,
            detail="Concept not found.",
        )

    # Recover the trusted evaluation criteria
    # generated and stored by the server.
    try:
        evaluation_criteria = json.loads(
            question.evaluation_criteria
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Stored evaluation criteria are invalid.",
        ) from None

    # IMPORTANT:
    # expected_answer and criteria come from the database,
    # NOT from the client.
    evaluation = evaluate_answer(
        question=question.question,
        expected_answer=question.expected_answer,
        student_answer=request.student_answer,
        evaluation_criteria=evaluation_criteria,
    )

    score = float(
        evaluation["score"]
    )

    result = evaluation["result"]

    misconception_text = evaluation.get(
        "misconception"
    )

    # Store diagnostic answer
    question.student_answer = request.student_answer
    question.score = score
    question.result = result
    question.answered = True

    # Lock the mastery row, store normal assessment history, then recompute
    # mastery from it (race-free; see app/services/mastery_service.py).
    mastery = lock_mastery(
        db,
        request.student_id,
        question.concept_id,
    )

    db.add(
        AssessmentAttempt(
            student_id=request.student_id,
            concept_id=question.concept_id,
            question=question.question,
            student_answer=request.student_answer,
            score=score,
            result=result,
        )
    )

    refresh_mastery(db, mastery)

    # Resolve previous misconceptions after a correct answer.
    if result == "correct":

        active_misconceptions = (
            db.query(Misconception)
            .filter(
                Misconception.student_id == request.student_id,
                Misconception.concept_id == question.concept_id,
                Misconception.resolved.is_(False),
            )
            .all()
        )

        for misconception in active_misconceptions:
            misconception.resolved = True

    # Store newly detected misconception.
    elif result in {
        "incorrect",
        "partially_correct",
    }:

        if misconception_text:

            db.add(
                Misconception(
                    student_id=request.student_id,
                    concept_id=question.concept_id,
                    description=misconception_text,
                    resolved=False,
                )
            )

    # Check whether every question in this session
    # has now been answered.
    # Make sure the current question update is written
# before checking whether the session is complete.
    db.flush()

    remaining_questions = (
        db.query(DiagnosticQuestion)
        .filter(
            DiagnosticQuestion.session_id == session.id,
            DiagnosticQuestion.answered.is_(False),
        )
        .count()
    )

    if remaining_questions == 0:
        session.status = "completed"

    db.commit()

    db.refresh(session)
    db.refresh(mastery)

    return DiagnosticSubmitResponse(
    question_id=question.id,
    concept_id=concept.id,
    concept=concept.name,
    score=score,
    result=result,
    feedback=evaluation.get("feedback", ""),
    misconception=misconception_text,
    mastery_score=mastery.mastery_score,
)