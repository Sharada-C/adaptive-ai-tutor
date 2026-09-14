from pydantic import BaseModel


class QuizRequest(BaseModel):
    student_id: int
    concept_id: int


class QuizQuestion(BaseModel):
    question: str
    expected_answer: str
    difficulty: str