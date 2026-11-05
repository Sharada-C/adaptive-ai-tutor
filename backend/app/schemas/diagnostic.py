from pydantic import BaseModel, Field


class DiagnosticStartRequest(BaseModel):
    student_id: int = Field(gt=0)
    subject_id: int = Field(gt=0)
    limit: int = Field(default=5, ge=1, le=20)


class DiagnosticQuestion(BaseModel):
    question_id: int
    concept_id: int
    concept: str
    question: str


class DiagnosticStartResponse(BaseModel):
    student_id: int
    subject_id: int
    subject: str
    session_id: int
    questions: list[DiagnosticQuestion]


class DiagnosticSubmitRequest(BaseModel):
    student_id: int = Field(gt=0)
    question_id: int = Field(gt=0)
    student_answer: str = Field(min_length=1, max_length=10000)


class DiagnosticSubmitResponse(BaseModel):
    question_id: int
    concept_id: int
    concept: str
    score: float
    result: str
    feedback: str
    misconception: str | None
    mastery_score: float