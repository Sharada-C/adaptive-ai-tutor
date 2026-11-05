from pathlib import Path

from sqlalchemy.orm import Session

from app.rag.knowledge_ingestion import ingest_text_for_concept


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
MAX_EXTRACTED_TEXT_LENGTH = 2_000_000  # 2 million characters


def extract_pdf_text(file_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError(
            "pypdf is not installed. Run: pip install pypdf"
        ) from error

    reader = PdfReader(str(file_path))

    pages = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            pages.append(page_text.strip())

    return "\n\n".join(pages).strip()


def extract_file_text(file_path: Path) -> str:
    extension = file_path.suffix.lower()

    if extension in SUPPORTED_TEXT_EXTENSIONS:
        text = file_path.read_text(encoding="utf-8").strip()

    elif extension == ".pdf":
        text = extract_pdf_text(file_path)

    else:
        raise ValueError(
            "Unsupported file type. "
            "Currently supported: .txt, .md, .markdown, .pdf"
        )

    if len(text) > MAX_EXTRACTED_TEXT_LENGTH:
        raise ValueError(
            "Extracted text is too large. "
            "Maximum supported size is 2 million characters."
        )

    return text


def ingest_file_for_concept(
    db: Session,
    concept_id: int,
    file_path: str,
    source: str | None = None,
    replace_source: bool = False,
) -> int:
    path = Path(file_path)

    if not path.exists():
        raise ValueError("Uploaded file could not be found.")

    if not path.is_file():
        raise ValueError("Uploaded path is not a file.")

    text = extract_file_text(path)

    if not text:
        raise ValueError(
            "No text could be extracted from the file."
        )

    source_name = source or path.name

    return ingest_text_for_concept(
        db=db,
        concept_id=concept_id,
        text=text,
        source=source_name,
        replace_source=replace_source,
    )