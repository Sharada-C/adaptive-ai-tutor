"""Tests for the endpoints and behaviours the frontend relies on."""

import uuid

import requests
from sqlalchemy import func
from fastapi.testclient import TestClient

from app.api import diagnostic, quiz
from app.db.database import SessionLocal
from app.main import app
from app.models import StudentProfile, User
from app.rag import retriever
from tests.conftest import token_for


client = TestClient(app)


# ---------------------------------------------------------------------
# Signed-in student
# ---------------------------------------------------------------------


def _delete_user(username: str) -> None:
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(func.lower(User.username) == username.lower())
            .first()
        )

        if user is not None:
            db.query(StudentProfile).filter(
                StudentProfile.user_id == user.id
            ).delete()
            db.delete(user)
            db.commit()

    finally:
        db.close()


def test_me_returns_the_ids_the_frontend_needs(test_student):
    response = client.get("/students/me")

    assert response.status_code == 200

    body = response.json()

    assert body["student_id"] == test_student
    assert body["username"] == "pytest_user"
    assert body["role"] == "student"
    assert body["learning_level"] in {"beginner", "intermediate", "advanced"}
    assert body["user_id"] > 0


def test_me_creates_a_missing_profile():
    # Staff accounts have no learner profile until they first need one.
    username = f"pytest_staff_{uuid.uuid4().hex[:8]}"
    headers = token_for(username, "instructor")

    try:
        response = client.get("/students/me", headers=headers)

        assert response.status_code == 200
        assert response.json()["student_id"] > 0
        assert response.json()["role"] == "instructor"

    finally:
        _delete_user(username)


def test_me_requires_sign_in():
    response = TestClient(app).get("/students/me")

    assert response.status_code == 401


def test_my_data_works_with_other_endpoints(test_student):
    mastery = client.get(f"/students/{test_student}/mastery")

    assert mastery.status_code == 200
    assert isinstance(mastery.json(), list)

    me = client.get("/students/me").json()

    # The profile endpoint is keyed by *user* id, not student id.
    profile = client.get(f"/students/{me['user_id']}/profile")

    assert profile.status_code == 200
    assert profile.json()["id"] == test_student


# ---------------------------------------------------------------------
# Learning level
# ---------------------------------------------------------------------


def test_update_learning_level(test_student):
    try:
        response = client.patch(
            f"/students/{test_student}/level",
            json={"learning_level": "advanced"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "student_id": test_student,
            "learning_level": "advanced",
        }

        db = SessionLocal()

        try:
            profile = db.get(StudentProfile, test_student)
            assert profile.learning_level == "advanced"

        finally:
            db.close()

    finally:
        client.patch(
            f"/students/{test_student}/level",
            json={"learning_level": "beginner"},
        )


def test_update_learning_level_rejects_unknown_level(test_student):
    response = client.patch(
        f"/students/{test_student}/level",
        json={"learning_level": "wizard"},
    )

    assert response.status_code == 422


def test_update_learning_level_unknown_student():
    # Not the caller's profile, so it is refused rather than "not found".
    response = client.patch(
        "/students/999999/level",
        json={"learning_level": "beginner"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------
# Subject-wide knowledge fallback
# ---------------------------------------------------------------------


def test_fallback_retrieval_uses_subject_when_concept_has_no_chunks(
    monkeypatch,
):
    calls = []

    def fake_retrieve(**kwargs):
        calls.append(kwargs)

        if kwargs.get("concept_id") is not None:
            return []

        return [{"chunk": object(), "similarity": 0.9, "source": "notes"}]

    monkeypatch.setattr(
        retriever,
        "retrieve_relevant_chunks_with_scores",
        fake_retrieve,
    )

    results = retriever.retrieve_with_subject_fallback(
        db=None,
        query="Routers",
        concept_id=7,
        subject_id=3,
        limit=2,
    )

    assert len(results) == 1
    assert calls[0]["concept_id"] == 7
    assert calls[1]["subject_id"] == 3
    assert calls[1].get("concept_id") is None


def test_fallback_retrieval_skips_subject_query_when_concept_matches(
    monkeypatch,
):
    calls = []

    def fake_retrieve(**kwargs):
        calls.append(kwargs)
        return [{"chunk": object(), "similarity": 0.9, "source": "notes"}]

    monkeypatch.setattr(
        retriever,
        "retrieve_relevant_chunks_with_scores",
        fake_retrieve,
    )

    retriever.retrieve_with_subject_fallback(
        db=None,
        query="Routers",
        concept_id=7,
        subject_id=3,
    )

    assert len(calls) == 1


def test_quiz_receives_subject_level_knowledge(monkeypatch, test_student):
    captured = {}

    class FakeChunk:
        content = "Routers forward packets between networks."

    def fake_retrieve(**kwargs):
        captured["retrieval"] = kwargs
        return [
            {
                "chunk": FakeChunk(),
                "similarity": 0.9,
                "source": "notes.pdf",
            }
        ]

    def fake_generate_quiz(**kwargs):
        captured["quiz"] = kwargs
        return {
            "question": "What do routers do?",
            "expected_answer": "They forward packets between networks.",
            "difficulty": "easy",
        }

    monkeypatch.setattr(
        quiz,
        "retrieve_with_subject_fallback",
        fake_retrieve,
    )
    monkeypatch.setattr(quiz, "generate_quiz", fake_generate_quiz)

    response = client.post(
        "/tutor/quiz",
        json={"student_id": test_student, "concept_id": 1},
    )

    assert response.status_code == 200
    assert response.json()["question"] == "What do routers do?"

    # The concept's subject must be passed so the fallback can work.
    assert captured["retrieval"]["subject_id"] == 1
    assert "Routers forward packets" in captured["quiz"]["knowledge_text"]


# ---------------------------------------------------------------------
# Readable errors instead of opaque 500s
# ---------------------------------------------------------------------


def test_quiz_generation_failure_is_reported_as_422(
    monkeypatch,
    test_student,
):
    monkeypatch.setattr(
        quiz,
        "retrieve_with_subject_fallback",
        lambda **kwargs: [],
    )

    def failing_generate_quiz(**kwargs):
        raise ValueError("No supported question could be produced.")

    monkeypatch.setattr(quiz, "generate_quiz", failing_generate_quiz)

    response = client.post(
        "/tutor/quiz",
        json={"student_id": test_student, "concept_id": 1},
    )

    assert response.status_code == 422
    assert "grounded quiz question" in response.json()["detail"]


def test_diagnostic_without_study_material_is_reported_as_422(
    monkeypatch,
    test_student,
):
    def no_material(**kwargs):
        raise ValueError(
            "No study material is available for 'Test Concept 1'."
        )

    monkeypatch.setattr(diagnostic, "generate_diagnostic", no_material)

    response = client.post(
        "/tutor/diagnostic/start",
        json={
            "student_id": test_student,
            "subject_id": 1,
            "limit": 2,
        },
    )

    assert response.status_code == 422
    assert "study material" in response.json()["detail"]


def test_unreachable_ollama_is_reported_as_503(monkeypatch, test_student):
    monkeypatch.setattr(
        quiz,
        "retrieve_with_subject_fallback",
        lambda **kwargs: [],
    )

    def ollama_down(**kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(quiz, "generate_quiz", ollama_down)

    response = client.post(
        "/tutor/quiz",
        json={"student_id": test_student, "concept_id": 1},
    )

    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_health_reports_llm_status_without_failing(monkeypatch):
    from app import main

    def ollama_down(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(main.requests, "get", ollama_down)

    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ok"
    assert body["llm"] == "unavailable"


# ---------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------


def test_cors_allows_the_vite_dev_origin():
    response = client.options(
        "/subjects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )
