from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str


class UserResponse(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class StudentProfileResponse(BaseModel):
    id: int
    user_id: int
    learning_level: str

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