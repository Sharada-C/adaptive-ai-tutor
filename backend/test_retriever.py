from app.db.database import SessionLocal
from app.rag.retriever import retrieve_relevant_chunks


def test_retrieve_relevant_chunks():
    db = SessionLocal()

    try:
        results = retrieve_relevant_chunks(
            db=db,
            query="What is the purpose of process scheduling?",
            concept_id=2,
            limit=3,
        )

        assert results is not None
        assert len(results) > 0
        assert len(results) <= 3

    finally:
        db.close()