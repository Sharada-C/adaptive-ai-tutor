from pydantic import BaseModel, Field


class DiagnosticStartRequest(BaseModel):
    student_id: int
    subject_id: int
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
    student_id: int
    question_id: int
    student_answer: str


class DiagnosticSubmitResponse(BaseModel):
    question_id: int
    concept_id: int
    concept: str
    score: float
    result: str
    feedback: str
    misconception: str | None
    mastery_score: float