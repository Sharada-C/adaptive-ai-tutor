from pydantic import BaseModel


class EvaluationRequest(BaseModel):
    student_id: int
    concept_id: int
    question: str
    expected_answer: str
    student_answer: str


class EvaluationResponse(BaseModel):
    score: float
    result: str
    feedback: str
    misconception: str | None = None

    next_action: str
    reason: str
    mastery_score: float

    prerequisite_concept_id: int | None = None
    prerequisite_concept: str | None = None
    prerequisite_mastery_score: float | None = None