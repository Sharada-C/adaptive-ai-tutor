import hashlib
import math
import re

import pytest

from app.db.database import SessionLocal
from app.rag import retrieval_eval
from app.rag.retrieval_eval import (
    CORPUS_FILE,
    QUESTIONS_FILE,
    first_gold_rank,
    format_report,
    load_json,
    summarise,
)


def fake_embedding(text: str) -> list[float]:
    """Deterministic hashed bag-of-words vector (768 dims, unit length)."""

    vector = [0.0] * 768

    for word in re.findall(r"[a-z]+", text.lower()):
        slot = int(hashlib.md5(word.encode()).hexdigest(), 16) % 768
        vector[slot] += 1.0

    norm = math.sqrt(sum(v * v for v in vector)) or 1.0

    return [v / norm for v in vector]


def test_first_gold_rank():
    assert first_gold_rank(["a", "b", "c"], ["b"]) == 2
    assert first_gold_rank(["a"], ["z"]) is None
    assert first_gold_rank([], ["z"]) is None


def test_summarise_metrics():
    questions = [
        {"question": "q1", "gold": ["a"]},
        {"question": "q2", "gold": ["b"]},
        {"question": "q3", "gold": ["c"]},
        {"question": "q4", "gold": []},
        {"question": "q5", "gold": []},
    ]
    ranked = [["a", "x"], ["x", "b"], ["x", "y", "z"], [], ["a"]]

    result = summarise(questions, ranked, limit=3)

    assert result["answerable"] == 3
    assert result["recall_at_3"] == pytest.approx(2 / 3)
    assert result["top1"] == pytest.approx(1 / 3)
    assert result["mrr"] == pytest.approx((1 + 0.5 + 0) / 3)
    assert [m["question"] for m in result["misses"]] == ["q3"]
    assert result["correctly_rejected"] == 1
    assert result["wrongly_answered"][0]["question"] == "q5"


def test_eval_data_is_consistent():
    corpus = load_json(CORPUS_FILE)
    questions = load_json(QUESTIONS_FILE)
    ids = {p["id"] for p in corpus}

    assert len(ids) == len(corpus)

    for q in questions:
        assert set(q["gold"]) <= ids

    assert any(not q["gold"] for q in questions)


def test_run_cleans_up_and_reports(monkeypatch):
    from app.models.curriculum import Subject
    from app.models.knowledge import KnowledgeChunk

    monkeypatch.setattr(
        "app.rag.knowledge_ingestion.generate_embedding", fake_embedding
    )
    monkeypatch.setattr(
        "app.rag.retriever.generate_embedding", fake_embedding
    )

    db = SessionLocal()

    try:
        before_subjects = db.query(Subject).count()
        before_chunks = db.query(KnowledgeChunk).count()

        report = retrieval_eval.run(
            db,
            load_json(CORPUS_FILE),
            load_json(QUESTIONS_FILE),
        )

        assert db.query(Subject).count() == before_subjects
        assert db.query(KnowledgeChunk).count() == before_chunks

        part = report["ranking_only"]
        assert 0.0 <= part["recall_at_3"] <= 1.0
        # Word-overlap embeddings should still find most passages.
        assert part["recall_at_3"] >= 0.5
        assert "Recall@3" in format_report(report)
    finally:
        db.close()
