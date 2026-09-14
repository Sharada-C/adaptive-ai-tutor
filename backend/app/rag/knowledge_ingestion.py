import re

from sqlalchemy.orm import Session

from app.models.curriculum import Concept
from app.models.knowledge import KnowledgeChunk
from app.rag.embedding_service import generate_embedding


def split_into_sections(text: str) -> list[str]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return []

    sections = []
    current_section = []

    for line in lines:
        is_heading = (
            len(line.split()) <= 8
            and not line.endswith(".")
            and not line.endswith(",")
            and not line.endswith(";")
            and not re.match(r"^[-*•]", line)
        )

        if is_heading and current_section:
            sections.append(" ".join(current_section))
            current_section = [line]
        else:
            current_section.append(line)

    if current_section:
        sections.append(" ".join(current_section))

    return sections


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")

    if overlap < 0:
        raise ValueError("overlap cannot be negative.")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    text = text.strip()

    if not text:
        return []

    sections = split_into_sections(text)

    chunks = []

    for section in sections:

        # Ignore title-only sections such as:
        # "COMPUTER NETWORKS"
        if len(section.split()) <= 2:
            continue

        words = section.split()

        if len(words) <= chunk_size:
            chunks.append(section)
            continue

        start = 0

        while start < len(words):
            end = start + chunk_size

            chunk = " ".join(words[start:end]).strip()

            if chunk:
                chunks.append(chunk)

            start += chunk_size - overlap

    return chunks


def ingest_text_for_concept(
    db: Session,
    concept_id: int,
    text: str,
    source: str,
    chunk_size: int = 500,
    overlap: int = 100,
    replace_source: bool = False,
) -> int:

    concept = db.get(Concept, concept_id)

    if not concept:
        raise ValueError(
            f"Concept with id {concept_id} does not exist."
        )

    text = text.strip()

    if not text:
        raise ValueError("Knowledge text cannot be empty.")

    source = source.strip()

    if not source:
        raise ValueError("Knowledge source cannot be empty.")

    chunks = chunk_text(
        text=text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    if not chunks:
        raise ValueError(
            "No valid knowledge chunks were produced."
        )

    try:

        # Only replace knowledge belonging to this
        # exact concept + source.
        if replace_source:
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.concept_id == concept_id,
                KnowledgeChunk.source == source,
            ).delete(
                synchronize_session=False
            )

        inserted = 0

        for chunk_text_value in chunks:

            # Preserve duplicate protection when
            # replace_source=False.
            if not replace_source:
                existing_chunk = (
                    db.query(KnowledgeChunk)
                    .filter(
                        KnowledgeChunk.concept_id == concept_id,
                        KnowledgeChunk.source == source,
                        KnowledgeChunk.content == chunk_text_value,
                    )
                    .first()
                )

                if existing_chunk:
                    continue

            embedding = generate_embedding(
                chunk_text_value
            )

            knowledge_chunk = KnowledgeChunk(
                concept_id=concept_id,
                content=chunk_text_value,
                source=source,
                embedding=embedding,
            )

            db.add(knowledge_chunk)
            inserted += 1

        db.commit()

        return inserted

    except Exception:
        db.rollback()
        raise