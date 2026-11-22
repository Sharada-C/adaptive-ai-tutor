from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import ensure_student_access, get_current_user
from app.models.student import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.student import (
    AssessmentAttempt,
    QuizQuestionRecord,
    Misconception,
    StudentProfile,
)
from app.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
)
from app.services.mastery_service import lock_mastery, refresh_mastery
from app.services.adaptation_service import determine_student_action
from app.tutor.evaluation_service import evaluate_answer


router = APIRouter(
    prefix="/tutor",
    tags=["Evaluation"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
)
def evaluate(
    request: EvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_student_access(
        db,
        current_user,
        request.student_id,
        allow_staff=False,
    )

    # ---------------------------------------------------------
    # 1. Verify student
    # ---------------------------------------------------------
    student = db.get(
        StudentProfile,
        request.student_id,
    )

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )

    # ---------------------------------------------------------
    # 2. Load the server-stored question (locked, so it is graded once)
    # ---------------------------------------------------------
    stored = db.execute(
        select(QuizQuestionRecord)
        .where(
            QuizQuestionRecord.id == request.question_id,
            QuizQuestionRecord.student_id == request.student_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if stored is None:
        raise HTTPException(
            status_code=404,
            detail="Quiz question not found",
        )

    if stored.answered:
        raise HTTPException(
            status_code=409,
            detail="This question has already been answered",
        )

    concept_id = stored.concept_id

    # ---------------------------------------------------------
    # 2b. Evaluate against the stored answer, never a client-sent one
    # ---------------------------------------------------------
    evaluation = evaluate_answer(
        question=stored.question_text,
        expected_answer=stored.expected_answer,
        student_answer=request.student_answer,
    )

    score = float(evaluation["score"])
    result = evaluation["result"]
    misconception_text = evaluation.get("misconception")

    # ---------------------------------------------------------
    # 3. Lock the mastery row, store the attempt, recompute mastery
    #    (race-free: see app/services/mastery_service.py)
    # ---------------------------------------------------------
    mastery = lock_mastery(
        db,
        request.student_id,
        concept_id,
    )

    db.add(
        AssessmentAttempt(
            student_id=request.student_id,
            concept_id=concept_id,
            question=stored.question_text,
            student_answer=request.student_answer,
            score=score,
            result=result,
        )
    )

    refresh_mastery(db, mastery)
    stored.answered = True

    # ---------------------------------------------------------
    # 6. Handle misconceptions
    # ---------------------------------------------------------

    if result == "correct":
    # A correct answer must never create a new misconception.
    #
    # Instead, it resolves currently active misconceptions
    # for this concept.

        active_misconceptions = (
            db.query(Misconception)
            .filter(
                Misconception.student_id == request.student_id,
                Misconception.concept_id == concept_id,
                Misconception.resolved.is_(False),
            )
            .all()
        )

        for misconception in active_misconceptions:
            misconception.resolved = True

    elif result == "partially_correct":
        # Partial answers should not automatically resolve
        # an existing misconception.
        #
        # Only create a new misconception if the same
        # misconception is not already active.

        if misconception_text:
            existing_misconception = (
                db.query(Misconception)
                .filter(
                    Misconception.student_id == request.student_id,
                    Misconception.concept_id == concept_id,
                    Misconception.description == misconception_text,
                    Misconception.resolved.is_(False),
                )
                .first()
            )

            if not existing_misconception:
                misconception = Misconception(
                    student_id=request.student_id,
                    concept_id=concept_id,
                    description=misconception_text,
                    resolved=False,
                )

                db.add(misconception)

    elif result == "incorrect":
        # Incorrect answers may create an active misconception
        # when the evaluator identifies one.
        #
        # Do not create a duplicate if the same misconception
        # is already active.

        if misconception_text:
            existing_misconception = (
                db.query(Misconception)
                .filter(
                    Misconception.student_id == request.student_id,
                    Misconception.concept_id == concept_id,
                    Misconception.description == misconception_text,
                    Misconception.resolved.is_(False),
                )
                .first()
            )

            if not existing_misconception:
                misconception = Misconception(
                    student_id=request.student_id,
                    concept_id=concept_id,
                    description=misconception_text,
                    resolved=False,
                )

                db.add(misconception)
    # ---------------------------------------------------------
    # 7. Commit before adaptive decision
    # ---------------------------------------------------------
    db.commit()

    # ---------------------------------------------------------
    # 8. Determine next action
    # ---------------------------------------------------------
    decision = determine_student_action(
        db=db,
        student_id=request.student_id,
        concept_id=concept_id,
    )

    # ---------------------------------------------------------
    # 9. Return result
    # ---------------------------------------------------------
    return EvaluationResponse(
        score=score,
        result=result,
        feedback=evaluation["feedback"],
        misconception=misconception_text,
        next_action=decision.action,
        reason=decision.reason,
        mastery_score=decision.mastery_score,
        prerequisite_concept_id=decision.prerequisite_concept_id,
        prerequisite_concept=decision.prerequisite_concept,
        prerequisite_mastery_score=decision.prerequisite_mastery_score,
    )