from pydantic import BaseModel, ConfigDict, Field


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


class TopicCourseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str = Field(min_length=3, max_length=100)


class MaterialSummary(BaseModel):
    articles: list[str]
    chunks: int


class TopicCourseResponse(BaseModel):
    subject_id: int
    subject: str
    description: str
    concepts_created: int
    created: bool
    material: MaterialSummary
    needs_material: bool
    message: str
