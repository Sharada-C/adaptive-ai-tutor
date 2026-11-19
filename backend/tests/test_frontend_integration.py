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


client = TestClient(app)


# ---------------------------------------------------------------------
# Student bootstrap
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


def test_bootstrap_creates_student_and_is_idempotent():
    username = f"pytest_bootstrap_{uuid.uuid4().hex[:8]}"

    try:
        first = client.post(
            "/students/bootstrap",
            json={"username": username},
        )

        assert first.status_code == 200

        created = first.json()

        assert created["username"] == username
        assert created["learning_level"] == "beginner"
        assert created["student_id"] > 0
        assert created["user_id"] > 0

        second = client.post(
            "/students/bootstrap",
            json={"username": username},
        )

        assert second.status_code == 200
        assert second.json() == {**created, "created": False}

    finally:
        _delete_user(username)


def test_bootstrap_reports_whether_profile_was_created():
    username = f"pytest_bootstrap_{uuid.uuid4().hex[:8]}"

    try:
        first = client.post(
            "/students/bootstrap",
            json={"username": username},
        ).json()

        second = client.post(
            "/students/bootstrap",
            json={"username": username},
        ).json()

        assert first["created"] is True
        assert second["created"] is False

    finally:
        _delete_user(username)


def test_bootstrap_ignores_case_and_surrounding_spaces():
    username = f"PyTest_Case_{uuid.uuid4().hex[:8]}"

    try:
        created = client.post(
            "/students/bootstrap",
            json={"username": username},
        ).json()

        again = client.post(
            "/students/bootstrap",
            json={"username": f"  {username.lower()}  "},
        ).json()

        assert again["student_id"] == created["student_id"]
        assert again["created"] is False
        # The name keeps the capitalisation it was created with.
        assert again["username"] == username

    finally:
        _delete_user(username)


def test_bootstrapped_student_works_with_other_endpoints():
    username = f"pytest_bootstrap_{uuid.uuid4().hex[:8]}"

    try:
        student = client.post(
            "/students/bootstrap",
            json={"username": username},
        ).json()

        mastery = client.get(
            f"/students/{student['student_id']}/mastery"
        )

        assert mastery.status_code == 200
        assert mastery.json() == []

        # The profile endpoint is keyed by *user* id, not student id.
        profile = client.get(
            f"/students/{student['user_id']}/profile"
        )

        assert profile.status_code == 200
        assert profile.json()["id"] == student["student_id"]

    finally:
        _delete_user(username)


def test_bootstrap_rejects_blank_username():
    response = client.post(
        "/students/bootstrap",
        json={"username": "   "},
    )

    assert response.status_code == 400


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
    response = client.patch(
        "/students/999999/level",
        json={"learning_level": "beginner"},
    )

    assert response.status_code == 404


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
