from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreate(BaseModel):
    concept_id: int = Field(gt=0)
    question: str = Field(min_length=1, max_length=5000)
    student_answer: str = Field(min_length=1, max_length=10000)
    score: float = Field(ge=0.0, le=1.0)
    result: str = Field(min_length=1, max_length=50)


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
    concept_id: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=5000)


class MisconceptionResponse(BaseModel):
    id: int
    student_id: int
    concept_id: int
    description: str
    resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)