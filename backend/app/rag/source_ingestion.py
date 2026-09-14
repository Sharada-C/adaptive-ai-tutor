from pathlib import Path

from sqlalchemy.orm import Session

from app.rag.knowledge_ingestion import ingest_text_for_concept


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


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
        return file_path.read_text(encoding="utf-8").strip()

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    raise ValueError(
        "Unsupported file type. "
        "Currently supported: .txt, .md, .markdown, .pdf"
    )

def ingest_file_for_concept(
    db: Session,
    concept_id: int,
    file_path: str,
    source: str | None = None,
    replace_source: bool = False,
) -> int:
    path = Path(file_path)

    if not path.exists():
        raise ValueError(
            f"File not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

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