from app.db.database import SessionLocal
from app.rag import retriever


def test_retrieve_relevant_chunks(monkeypatch):
    def fake_embedding(text):
        return [0.0] * 768

    monkeypatch.setattr(
        retriever,
        "generate_embedding",
        fake_embedding,
    )

    db = SessionLocal()

    try:
        results = retriever.retrieve_relevant_chunks(
            db=db,
            query="What is the purpose of process scheduling?",
            concept_id=2,
            limit=3,
        )

        assert results is not None
        assert len(results) <= 3

    finally:
        db.close()