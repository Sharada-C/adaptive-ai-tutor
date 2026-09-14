from fastapi.testclient import TestClient

from app.main import app
from app.api import diagnostic

client = TestClient(app)


def test_diagnostic_start(monkeypatch,test_student):
    def fake_generate_diagnostic(db, student_id, subject_id, student_level, limit):
        return [
            {
                "concept_id": 1,
                "concept": "Process Management",
                "question": "What is process management?",
                "expected_answer": "It is the management of processes.",
                "evaluation_criteria": ["Defines process management"],
                "misconception_guidance": "Clarify the role of process management.",
            },
            {
                "concept_id": 2,
                "concept": "Process Scheduling",
                "question": "What is process scheduling?",
                "expected_answer": "It determines which process runs.",
                "evaluation_criteria": ["Explains process scheduling"],
                "misconception_guidance": "Clarify the purpose of scheduling.",
            },
        ][:limit]

    monkeypatch.setattr(
        diagnostic,
        "generate_diagnostic",
        fake_generate_diagnostic,
    )

    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": test_student,
            "subject_id": 1,
            "limit": 2,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["student_id"] == test_student
    assert data["subject_id"] == 1
    assert "session_id" in data
    assert len(data["questions"]) == 2

    for question in data["questions"]:
        assert "question_id" in question
        assert "concept_id" in question
        assert "concept" in question
        assert "question" in question
        assert "expected_answer" not in question