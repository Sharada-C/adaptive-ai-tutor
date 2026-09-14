from fastapi.testclient import TestClient

from app.main import app
from app.api import evaluation


client = TestClient(app)


def test_evaluate_updates_mastery(monkeypatch):
    def fake_evaluate_answer(
        question,
        expected_answer,
        student_answer,
    ):
        return {
            "score": 0.9,
            "result": "correct",
            "feedback": "Good answer.",
            "misconception": None,
        }

    monkeypatch.setattr(
        evaluation,
        "evaluate_answer",
        fake_evaluate_answer,
    )

    response = client.post(
        "/tutor/evaluate",
        json={
            "student_id": 1,
            "concept_id": 1,
            "question": "What is process management?",
            "expected_answer": "It manages processes.",
            "student_answer": "It manages processes.",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["score"] == 0.9
    assert data["result"] == "correct"
    assert data["feedback"] == "Good answer."
    assert data["mastery_score"] >= 0.0
    assert data["mastery_score"] <= 1.0