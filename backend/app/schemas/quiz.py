from pydantic import BaseModel


class QuizRequest(BaseModel):
    student_id: int
    concept_id: int


class QuizQuestion(BaseModel):
    """What the browser receives. The expected answer stays on the server."""

    question_id: int
    question: str
    difficulty: str
