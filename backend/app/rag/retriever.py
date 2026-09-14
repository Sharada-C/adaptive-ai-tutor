from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk
from app.rag.embedding_service import generate_embedding


DEFAULT_LIMIT = 3
DEFAULT_SIMILARITY_THRESHOLD = 0.50


def retrieve_relevant_chunks(
    db: Session,
    query: str,
    concept_id: int | None = None,
    limit: int = DEFAULT_LIMIT,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[KnowledgeChunk]:
    """
    Retrieve relevant knowledge chunks using pgvector cosine similarity.

    Only chunks whose similarity is at or above the configured
    threshold are returned.
    """

    if not query.strip():
        return []

    if limit <= 0:
        raise ValueError("limit must be greater than 0.")

    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError(
            "similarity_threshold must be between 0 and 1."
        )

    query_embedding = generate_embedding(query)

    similarity = (
        1
        - KnowledgeChunk.embedding.cosine_distance(
            query_embedding
        )
    )

    db_query = db.query(
        KnowledgeChunk,
        similarity.label("similarity"),
    )

    if concept_id is not None:
        db_query = db_query.filter(
            KnowledgeChunk.concept_id == concept_id
        )

    results = (
        db_query
        .filter(similarity >= similarity_threshold)
        .order_by(similarity.desc())
        .limit(limit)
        .all()
    )

    return [
        chunk
        for chunk, _similarity in results
    ]


def retrieve_relevant_chunks_with_scores(
    db: Session,
    query: str,
    concept_id: int | None = None,
    limit: int = DEFAULT_LIMIT,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    Retrieve knowledge chunks together with similarity scores
    and source metadata.
    """

    if not query.strip():
        return []

    if limit <= 0:
        raise ValueError("limit must be greater than 0.")

    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError(
            "similarity_threshold must be between 0 and 1."
        )

    query_embedding = generate_embedding(query)

    similarity = (
        1
        - KnowledgeChunk.embedding.cosine_distance(
            query_embedding
        )
    )

    db_query = db.query(
        KnowledgeChunk,
        similarity.label("similarity"),
    )

    if concept_id is not None:
        db_query = db_query.filter(
            KnowledgeChunk.concept_id == concept_id
        )

    results = (
        db_query
        .filter(similarity >= similarity_threshold)
        .order_by(similarity.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "chunk": chunk,
            "similarity": float(score),
            "source": chunk.source,
            "concept_id": chunk.concept_id,
        }
        for chunk, score in results
    ]