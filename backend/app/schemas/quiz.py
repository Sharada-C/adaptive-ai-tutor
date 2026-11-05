from pydantic import BaseModel, Field


class QuizRequest(BaseModel):
    student_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)


class QuizQuestion(BaseModel):
    question: str
    expected_answer: str
    difficulty: str