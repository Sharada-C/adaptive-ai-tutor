"""Timeout, retry and fallback-mode behaviour for Ollama calls."""

from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

from app.api import tutor as tutor_api
from app.core.config import settings
from app.main import app
from app.services import ollama_client
from app.tutor import tutor_service
from tests.conftest import token_for

client = TestClient(app)


class Resp:
    def __init__(self, payload=None, status=200):
        self.payload = payload or {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"{self.status_code}", response=SimpleNamespace(status_code=self.status_code)
            )

    def json(self):
        return self.payload


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(ollama_client.time, "sleep", slept.append)
    return slept


def _script(monkeypatch, outcomes):
    calls = []

    def fake(url, json, timeout):
        calls.append({"url": url, "timeout": timeout})
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(ollama_client.requests, "post", fake)
    return calls


def test_timeout_comes_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "ollama_timeout_seconds", 7.5)
    calls = _script(monkeypatch, [Resp({"ok": 1})])

    assert ollama_client.post_json("http://x/api", {}) == {"ok": 1}
    assert calls[0]["timeout"] == 7.5


def test_one_retry_with_backoff_after_a_connection_error(monkeypatch, no_sleep):
    calls = _script(monkeypatch, [requests.ConnectionError("down"), Resp({"ok": 1})])

    assert ollama_client.post_json("http://x/api", {}) == {"ok": 1}
    assert len(calls) == 2
    assert no_sleep == [settings.ollama_retry_backoff_seconds]


def test_retries_on_timeout_and_server_errors(monkeypatch, no_sleep):
    calls = _script(monkeypatch, [requests.Timeout("slow"), Resp(status=503), Resp({"ok": 1})])
    monkeypatch.setattr(settings, "ollama_retries", 2)

    assert ollama_client.post_json("http://x/api", {}) == {"ok": 1}
    assert len(calls) == 3


def test_gives_up_after_the_configured_retries(monkeypatch, no_sleep):
    calls = _script(monkeypatch, [requests.ConnectionError("down")])

    with pytest.raises(requests.ConnectionError):
        ollama_client.post_json("http://x/api", {})

    assert len(calls) == 2  # first try + 1 retry


def test_client_errors_are_not_retried(monkeypatch, no_sleep):
    calls = _script(monkeypatch, [Resp(status=404)])

    with pytest.raises(requests.HTTPError):
        ollama_client.post_json("http://x/api", {})

    assert len(calls) == 1
    assert no_sleep == []


def test_llm_and_embedding_calls_both_use_the_shared_client(monkeypatch, no_sleep):
    _script(monkeypatch, [requests.ConnectionError("x"), Resp({"response": "hi"})])
    assert tutor_service.generate_response("p") == "hi"

    from app.rag import embedding_service

    _script(monkeypatch, [requests.ConnectionError("x"), Resp({"embedding": [0.0] * 768})])
    assert len(embedding_service.generate_embedding("t")) == 768


# ---- mode flag ---------------------------------------------------------

EVIDENCE = "A process is a program in execution. The scheduler picks the next ready process."


def test_grounded_llm_answer_is_reported_as_llm(monkeypatch):
    monkeypatch.setattr(
        tutor_service, "generate_response",
        lambda prompt: "A process is a program in execution.",
    )
    result = tutor_service.grounded_response("p", EVIDENCE)

    assert result.mode == "llm"
    assert result.text == "A process is a program in execution."


def test_ungrounded_llm_answer_falls_back_to_extractive(monkeypatch):
    monkeypatch.setattr(
        tutor_service, "generate_response",
        lambda prompt: "Processes always use quantum computers to run faster.",
    )
    result = tutor_service.grounded_response("p", EVIDENCE)

    assert result.mode == "extractive"
    assert "program in execution" in result.text


def test_no_evidence_is_extractive():
    assert tutor_service.grounded_response("p", "  ").mode == "extractive"


@pytest.mark.parametrize("llm_text,mode", [
    ("A process is a program in execution.", "llm"),
    ("Processes always use quantum computers to run faster.", "extractive"),
])
def test_lesson_endpoint_reports_the_mode(monkeypatch, test_student, llm_text, mode):
    chunk = SimpleNamespace(content=EVIDENCE)
    monkeypatch.setattr(
        tutor_api, "retrieve_with_subject_fallback",
        lambda **kw: [{"chunk": chunk, "source": "notes", "similarity": 0.9}],
    )
    monkeypatch.setattr(tutor_service, "generate_response", lambda prompt: llm_text)

    response = client.post(
        "/tutor/lesson",
        headers=token_for("pytest_user"),
        json={"student_id": test_student, "concept_id": 1},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == mode
