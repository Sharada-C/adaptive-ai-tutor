from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SubjectMasteryResponse(BaseModel):
    subject_id: int
    subject_name: str
    mastery: float


class ConceptStrengthResponse(BaseModel):
    concept_id: int
    concept_name: str
    subject_name: str
    mastery: float


class StudentProfileResponse(BaseModel):
    id: int
    user_id: int
    learning_level: str
    overall_mastery: float
    subject_mastery: list[SubjectMasteryResponse]
    concepts_to_strengthen: list[ConceptStrengthResponse]

    model_config = ConfigDict(from_attributes=True)


class MasteryUpdate(BaseModel):
    concept_id: int
    mastery_score: float
    attempts: int = 0
    correct_answers: int = 0


class MasteryResponse(BaseModel):
    id: int
    student_id: int
    concept_id: int
    mastery_score: float
    attempts: int
    correct_answers: int

    model_config = ConfigDict(from_attributes=True)

class StudentBootstrapResponse(BaseModel):
    """Identifiers the frontend needs to talk to the rest of the API.

    ``student_id`` is the StudentProfile id used by the tutor, planner,
    mastery and diagnostic endpoints. ``user_id`` is only needed for
    ``GET /students/{user_id}/profile``.
    """

    user_id: int
    student_id: int
    username: str
    role: str
    learning_level: str


class LearningLevelUpdate(BaseModel):
    learning_level: Literal[
        "beginner",
        "intermediate",
        "advanced",
    ]


class LearningLevelResponse(BaseModel):
    student_id: int
    learning_level: str
