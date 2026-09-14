from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.rag.knowledge_ingestion import ingest_text_for_concept


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base"],
)


class KnowledgeIngestRequest(BaseModel):
    concept_id: int
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)


class KnowledgeIngestResponse(BaseModel):
    concept_id: int
    source: str
    chunks_inserted: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/ingest", response_model=KnowledgeIngestResponse, status_code=201)
def ingest_knowledge(
    request: KnowledgeIngestRequest,
    db: Session = Depends(get_db),
):
    try:
        inserted = ingest_text_for_concept(
            db=db,
            concept_id=request.concept_id,
            text=request.text,
            source=request.source,
        )

        return KnowledgeIngestResponse(
            concept_id=request.concept_id,
            source=request.source,
            chunks_inserted=inserted,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )