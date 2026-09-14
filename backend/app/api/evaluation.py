from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.student import (
    AssessmentAttempt,
    ConceptMastery,
    Misconception,
    StudentProfile,
)
from app.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
)
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
):
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
    # 2. Evaluate answer using LLM
    # ---------------------------------------------------------
    evaluation = evaluate_answer(
        question=request.question,
        expected_answer=request.expected_answer,
        student_answer=request.student_answer,
    )

    score = float(evaluation["score"])
    result = evaluation["result"]
    misconception_text = evaluation.get("misconception")

    # ---------------------------------------------------------
    # 3. Store assessment attempt
    # ---------------------------------------------------------
    attempt = AssessmentAttempt(
        student_id=request.student_id,
        concept_id=request.concept_id,
        question=request.question,
        student_answer=request.student_answer,
        score=score,
        result=result,
    )

    db.add(attempt)

    # ---------------------------------------------------------
    # 4. Get or create mastery record
    # ---------------------------------------------------------
    mastery = (
        db.query(ConceptMastery)
        .filter(
            ConceptMastery.student_id == request.student_id,
            ConceptMastery.concept_id == request.concept_id,
        )
        .first()
    )

    if not mastery:
        mastery = ConceptMastery(
            student_id=request.student_id,
            concept_id=request.concept_id,
            mastery_score=0.0,
            attempts=0,
            correct_answers=0,
        )

        db.add(mastery)

    # ---------------------------------------------------------
    # 5. Update mastery
    # ---------------------------------------------------------
    mastery.attempts += 1

    if result == "correct":
        mastery.correct_answers += 1

    # Flush pending changes so the current assessment attempt
    # is available when calculating recent performance.
    db.flush()

    # Get the student's five most recent attempts
    # for this concept.
    recent_attempts = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.student_id == request.student_id,
            AssessmentAttempt.concept_id == request.concept_id,
        )
        .order_by(
            AssessmentAttempt.created_at.desc(),
            AssessmentAttempt.id.desc(),
        )
        .limit(5)
        .all()
    )

    # Reverse so scores are ordered:
    #
    # oldest -> newest
    #
    # This allows newer attempts to receive larger weights.
    scores = [
        assessment.score
        for assessment in reversed(recent_attempts)
    ]

    if scores:
        # Example for five attempts:
        #
        # oldest                 newest
        #   ↓                       ↓
        #   1       2       3       4       5
        #
        # Newer performance has more influence.
        weights = list(range(1, len(scores) + 1))

        weighted_sum = sum(
            score_value * weight
            for score_value, weight in zip(
                scores,
                weights,
            )
        )

        mastery.mastery_score = (
            weighted_sum / sum(weights)
        )

    # Keep mastery between 0 and 1.
    mastery.mastery_score = max(
        0.0,
        min(
            1.0,
            mastery.mastery_score,
        ),
    )

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
                Misconception.concept_id == request.concept_id,
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
    # However, if the evaluator identifies a genuine new
    # misconception, store it.

        if misconception_text:
            misconception = Misconception(
                student_id=request.student_id,
                concept_id=request.concept_id,
                description=misconception_text,
                resolved=False,
            )

            db.add(misconception)

    elif result == "incorrect":
    # Incorrect answers may create an active misconception
    # when the evaluator identified one.

        if misconception_text:
            misconception = Misconception(
                student_id=request.student_id,
                concept_id=request.concept_id,
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
        concept_id=request.concept_id,
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