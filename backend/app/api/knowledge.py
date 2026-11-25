from pathlib import Path
from tempfile import NamedTemporaryFile
from pypdf.errors import PdfReadError, PdfStreamError
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.api.deps import (
    ensure_can_add_material,
    ensure_concept_access,
    ensure_subject_access,
    get_current_user,
)
from app.models.student import User
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.rag.knowledge_ingestion import (
    ingest_text_for_concept,
    ingest_text_for_subject,
)


router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base"],
)


ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf"}
UPLOAD_ERRORS = (PdfReadError, PdfStreamError)


def _too_large() -> HTTPException:
    limit_mb = settings.max_upload_bytes // (1024 * 1024)
    return HTTPException(
        status_code=413,
        detail=f"File is too large. The limit is {limit_mb} MB.",
    )


def _save_upload(file: UploadFile) -> Path:
    """Copy an upload to a temp file, refusing anything over the size cap.

    The declared Content-Length is checked first (cheap rejection), then the
    bytes actually received are counted while streaming, so a lying client
    cannot push past the limit and the file is never loaded into memory.
    """

    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Currently supported: "
                ".txt, .md, .markdown, .pdf"
            ),
        )

    if file.size is not None and file.size > settings.max_upload_bytes:
        raise _too_large()

    total = 0

    with NamedTemporaryFile(suffix=extension, delete=False) as temporary_file:
        path = Path(temporary_file.name)

        try:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)

                if total > settings.max_upload_bytes:
                    raise _too_large()

                temporary_file.write(chunk)
        except BaseException:
            temporary_file.close()
            path.unlink(missing_ok=True)
            raise

    return path


def _authorize_subject(db: Session, user: User, subject_id: int) -> None:
    """Staff may add to shared courses; students only to their own."""

    subject = ensure_subject_access(db, user, subject_id)
    ensure_can_add_material(db, user, subject)


def _authorize_concept(db: Session, user: User, concept_id: int) -> None:
    concept = ensure_concept_access(db, user, concept_id)
    ensure_can_add_material(db, user, concept.subject)


def _unreadable_pdf() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail="The PDF could not be read. It may be corrupt or damaged.",
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
    user: User = Depends(get_current_user),
):
    _authorize_concept(db, user, request.concept_id)

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
        ) from error
@router.post("/upload", response_model=KnowledgeIngestResponse, status_code=201)
def upload_knowledge_file(
    concept_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _authorize_concept(db, user, concept_id)
    temporary_path = None

    try:
        temporary_path = _save_upload(file)

        from app.rag.source_ingestion import ingest_file_for_concept

        inserted = ingest_file_for_concept(
            db=db,
            concept_id=concept_id,
            file_path=str(temporary_path),
            source=file.filename,
        )

        return KnowledgeIngestResponse(
            concept_id=concept_id,
            source=file.filename,
            chunks_inserted=inserted,
        )

    except UPLOAD_ERRORS:
        raise _unreadable_pdf() from None


    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        file.file.close()


@router.post(
    "/ingest/subject",
    response_model=SubjectKnowledgeIngestResponse,
    status_code=201,
)
def ingest_subject_knowledge(
    request: SubjectKnowledgeIngestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _authorize_subject(db, user, request.subject_id)

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
        ) from error

@router.post(
    "/upload/subject",
    response_model=SubjectKnowledgeIngestResponse,
    status_code=201,
)
def upload_subject_knowledge_file(
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _authorize_subject(db, user, subject_id)
    temporary_path = None

    try:
        temporary_path = _save_upload(file)

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

    except UPLOAD_ERRORS:
        raise _unreadable_pdf() from None

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        file.file.close()