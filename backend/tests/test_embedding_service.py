import pytest
import requests

from app.rag import embedding_service
from app.services import ollama_client


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")

    def json(self):
        return self._payload


def _post(monkeypatch, response):
    sent = {}

    def fake(url, json, timeout):
        sent.update(url=url, json=json, timeout=timeout)
        return response

    monkeypatch.setattr(ollama_client.requests, "post", fake)
    return sent


def test_embedding_is_requested_from_ollama(monkeypatch):
    sent = _post(monkeypatch, FakeResponse({"embedding": [0.1] * 768}))

    assert embedding_service.generate_embedding("hello") == [0.1] * 768
    assert sent["url"].endswith("/api/embeddings")
    assert sent["json"]["prompt"] == "hello"


@pytest.mark.parametrize(
    "payload,message",
    [({}, "no embedding"), ({"embedding": [0.1] * 10}, "768-dimensional")],
)
def test_bad_embeddings_are_rejected(monkeypatch, payload, message):
    _post(monkeypatch, FakeResponse(payload))

    with pytest.raises(RuntimeError, match=message):
        embedding_service.generate_embedding("hello")


def test_http_errors_propagate(monkeypatch):
    monkeypatch.setattr(ollama_client.settings, "ollama_retries", 0)
    _post(monkeypatch, FakeResponse({}, status=500))

    with pytest.raises(requests.HTTPError):
        embedding_service.generate_embedding("hello")
