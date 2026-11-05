from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_user
from app.models.student import User
from app.rag.knowledge_ingestion import (
    ingest_text_for_concept,
    ingest_text_for_subject,
)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

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




@router.post("/ingest", response_model=KnowledgeIngestResponse, status_code=201)
def ingest_knowledge(
    request: KnowledgeIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can modify the knowledge base",
        )
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

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid knowledge data.",
        )
@router.post("/upload", response_model=KnowledgeIngestResponse, status_code=201)
def upload_knowledge_file(
    concept_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can modify the knowledge base",
            )
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
            total_size = 0

            while chunk := file.file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                    detail="Uploaded file is too large. Maximum size is 10 MB.",
                    )

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

    except ValueError:
        if "temporary_path" in locals():
            temporary_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail="Invalid uploaded knowledge file.",
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can modify the knowledge base",
            )
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

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid subject knowledge data.",
        )

@router.post(
    "/upload/subject",
    response_model=SubjectKnowledgeIngestResponse,
    status_code=201,
)
def upload_subject_knowledge_file(
    subject_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    temporary_path = None
    if current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only admins can modify the knowledge base",
            )
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
            total_size = 0

            while chunk := file.file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Uploaded file is too large. Maximum size is 10 MB.",
                    )

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

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid uploaded subject knowledge file.",
        )

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        file.file.close()