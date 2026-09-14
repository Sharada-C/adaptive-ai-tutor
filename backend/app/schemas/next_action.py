from pydantic import BaseModel


class NextActionResponse(BaseModel):
    action: str
    reason: str
    concept_id: int
    concept: str
    mastery_score: float

    prerequisite_concept_id: int | None = None
    prerequisite_concept: str | None = None
    prerequisite_mastery_score: float | None = None