from pydantic import BaseModel, Field


class CurriculumGenerateRequest(BaseModel):
    topic: str = Field(
        min_length=1,
        max_length=100,
    )


class GeneratedConcept(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=150,
    )

    description: str = Field(
        min_length=1,
    )

    prerequisites: list[str] = []


class GeneratedCurriculum(BaseModel):
    subject: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str = Field(
        min_length=1,
    )

    concepts: list[GeneratedConcept] = Field(
        min_length=1,
    )


class SavedCurriculumResponse(BaseModel):
    subject_id: int
    subject: str
    description: str
    concepts_created: int