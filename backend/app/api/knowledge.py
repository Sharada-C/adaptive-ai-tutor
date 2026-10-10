from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.rag.knowledge_ingestion import (
    ingest_text_for_concept,
    ingest_text_for_subject,
)


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base"],
)


class KnowledgeIngestRequest(BaseModel):
    concept_id: int
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
class SubjectKnowledgeIngestRequest(BaseModel):
    subject_id: int
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)


class KnowledgeIngestResponse(BaseModel):
    concept_id: int
    source: str
    chunks_inserted: int

class SubjectKnowledgeIngestResponse(BaseModel):
    subject_id: int
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
@router.post("/upload", response_model=KnowledgeIngestResponse, status_code=201)
def upload_knowledge_file(
    concept_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        extension = Path(file.filename or "").suffix.lower()

        if extension not in {".txt", ".md", ".markdown", ".pdf"}:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Currently supported: .txt, .md, .markdown, .pdf",
            )

        with NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            while chunk := file.file.read(1024 * 1024):
                temporary_file.write(chunk)

        from app.rag.source_ingestion import ingest_file_for_concept

        inserted = ingest_file_for_concept(
            db=db,
            concept_id=concept_id,
            file_path=str(temporary_path),
            source=file.filename,
        )

        temporary_path.unlink(missing_ok=True)

        return KnowledgeIngestResponse(
            concept_id=concept_id,
            source=file.filename,
            chunks_inserted=inserted,
        )

    except ValueError as error:
        if "temporary_path" in locals():
            temporary_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        if "temporary_path" in locals():
            temporary_path.unlink(missing_ok=True)

        raise

@router.post(
    "/ingest/subject",
    response_model=SubjectKnowledgeIngestResponse,
    status_code=201,
)
def ingest_subject_knowledge(
    request: SubjectKnowledgeIngestRequest,
    db: Session = Depends(get_db),
):
    try:
        inserted = ingest_text_for_subject(
            db=db,
            subject_id=request.subject_id,
            text=request.text,
            source=request.source,
        )

        return SubjectKnowledgeIngestResponse(
            subject_id=request.subject_id,
            source=request.source,
            chunks_inserted=inserted,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

@router.post(
    "/upload/subject",
    response_model=SubjectKnowledgeIngestResponse,
    status_code=201,
)
def upload_subject_knowledge_file(
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    temporary_path = None

    try:
        extension = Path(file.filename or "").suffix.lower()

        if extension not in {".txt", ".md", ".markdown", ".pdf"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported file type. Currently supported: "
                    ".txt, .md, .markdown, .pdf"
                ),
            )

        with NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            while chunk := file.file.read(1024 * 1024):
                temporary_file.write(chunk)

        from app.rag.source_ingestion import extract_file_text

        extracted_text = extract_file_text(temporary_path)

        inserted = ingest_text_for_subject(
            db=db,
            subject_id=subject_id,
            text=extracted_text,
            source=file.filename or "uploaded-document",
        )

        return SubjectKnowledgeIngestResponse(
            subject_id=subject_id,
            source=file.filename or "uploaded-document",
            chunks_inserted=inserted,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        file.file.close()