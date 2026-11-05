from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    student_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    question: str = Field(min_length=1, max_length=5000)
    expected_answer: str = Field(min_length=1, max_length=10000)
    student_answer: str = Field(min_length=1, max_length=10000)


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