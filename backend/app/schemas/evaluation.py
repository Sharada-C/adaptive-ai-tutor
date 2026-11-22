from pydantic import BaseModel


class EvaluationRequest(BaseModel):
    """Only the question id and the student's answer are trusted.

    The question text, concept and expected answer are read from the
    ``quiz_questions`` row the server stored. Any extra fields a client sends
    (``expected_answer``, ``question``, ``concept_id``) are ignored.
    """

    student_id: int
    question_id: int
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