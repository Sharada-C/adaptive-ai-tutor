"""Uploads: bounded size, and bad PDFs are a client error, not a 500."""

import pytest
from fastapi.testclient import TestClient

from app.api import knowledge
from app.main import app
from tests.conftest import token_for

client = TestClient(app, raise_server_exceptions=False)

ONE_MB = 1024 * 1024


@pytest.fixture
def staff():
    return token_for("pytest_instructor", "instructor")


@pytest.fixture(autouse=True)
def no_embedding(monkeypatch):
    """Never reach Ollama: pretend ingestion succeeded."""
    monkeypatch.setattr(
        knowledge, "ingest_text_for_subject", lambda **kw: 1
    )
    monkeypatch.setattr(
        "app.rag.source_ingestion.ingest_text_for_concept",
        lambda **kw: 1,
    )


@pytest.mark.parametrize(
    "url,field",
    [("/knowledge/upload/subject", "subject_id"), ("/knowledge/upload", "concept_id")],
)
def test_corrupt_pdf_is_422(staff, url, field):
    response = client.post(
        url,
        headers=staff,
        data={field: "1"},
        files={"file": ("broken.pdf", b"%PDF-1.4 this is not a real pdf", "application/pdf")},
    )

    assert response.status_code == 422
    assert "PDF" in response.json()["detail"]


@pytest.mark.parametrize(
    "url,field",
    [("/knowledge/upload/subject", "subject_id"), ("/knowledge/upload", "concept_id")],
)
def test_oversized_upload_is_413(staff, url, field):
    big = b"a" * (10 * ONE_MB + 1)

    response = client.post(
        url,
        headers=staff,
        data={field: "1"},
        files={"file": ("big.txt", big, "text/plain")},
    )

    assert response.status_code == 413


def test_upload_at_the_limit_is_accepted(staff):
    ok = b"word " * 1000

    response = client.post(
        "/knowledge/upload/subject",
        headers=staff,
        data={"subject_id": "1"},
        files={"file": ("ok.txt", ok, "text/plain")},
    )

    assert response.status_code == 201


def test_oversized_upload_leaves_no_temp_file(staff, tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    client.post(
        "/knowledge/upload/subject",
        headers=staff,
        data={"subject_id": "1"},
        files={"file": ("big.txt", b"a" * (10 * ONE_MB + 1), "text/plain")},
    )

    assert list(tmp_path.iterdir()) == []
