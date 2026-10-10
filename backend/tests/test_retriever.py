
from unittest.mock import patch

from app.rag.retriever import retrieve_relevant_chunks_with_scores


def test_retriever_uses_similarity_threshold():
    """Chunks below the threshold must not be returned."""

    class FakeQuery:
        def __init__(self):
            self.filters = []
            self.ordered = False
            self.limit_value = None

        def filter(self, condition):
            self.filters.append(condition)
            return self

        def order_by(self, value):
            self.ordered = True
            return self

        def limit(self, value):
            self.limit_value = value
            return self

        def all(self):
            return []

    class FakeDB:
        def __init__(self):
            self.query_object = FakeQuery()

        def query(self, *args):
            return self.query_object

    db = FakeDB()

    with patch(
        "app.rag.retriever.generate_embedding",
        return_value=[0.0] * 768,
    ):
        results = retrieve_relevant_chunks_with_scores(
            db=db,
            query="Explain focal length and perspective",
            concept_id=27,
            subject_id=5,
            limit=3,
            similarity_threshold=0.65,
        )

    assert results == []
    assert db.query_object.ordered is True
    assert db.query_object.limit_value == 3
    assert len(db.query_object.filters) == 2
