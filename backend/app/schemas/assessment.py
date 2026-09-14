from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssessmentCreate(BaseModel):
    concept_id: int
    question: str
    student_answer: str
    score: float
    result: str


class AssessmentResponse(BaseModel):
    id: int
    student_id: int
    concept_id: int
    question: str
    student_answer: str
    score: float
    result: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MisconceptionCreate(BaseModel):
    concept_id: int
    description: str


class MisconceptionResponse(BaseModel):
    id: int
    student_id: int
    concept_id: int
    description: str
    resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)