from pydantic import BaseModel, ConfigDict


class SubjectCreate(BaseModel):
    name: str
    description: str | None = None


class SubjectResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class ConceptCreate(BaseModel):
    name: str
    description: str | None = None


class ConceptResponse(BaseModel):
    id: int
    subject_id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)