"""Chunking and ingestion, with the embedding model mocked (no Ollama)."""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app.models import Concept, Subject
from app.models.knowledge import KnowledgeChunk
from app.rag import ingest, knowledge_ingestion, source_ingestion
from app.rag.knowledge_ingestion import (
    chunk_text,
    ingest_text_for_concept,
    ingest_text_for_subject,
    split_into_sections,
)

FAKE_VECTOR = [0.01] * 768


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    calls = []

    def fake(text):
        calls.append(text)
        return FAKE_VECTOR

    monkeypatch.setattr(knowledge_ingestion, "generate_embedding", fake)
    monkeypatch.setattr(ingest, "generate_embedding", fake)
    return calls


@pytest.fixture
def curriculum():
    db = SessionLocal()
    subject = Subject(name=f"RAG Subject {uuid.uuid4().hex[:8]}", description="t")
    db.add(subject)
    db.flush()
    concept = Concept(subject_id=subject.id, name="C", description="c")
    db.add(concept)
    db.commit()
    ids = (subject.id, concept.id)
    yield ids
    db.rollback()
    db.query(KnowledgeChunk).filter(
        (KnowledgeChunk.subject_id == ids[0]) | (KnowledgeChunk.concept_id == ids[1])
    ).delete(synchronize_session=False)
    db.query(Concept).filter_by(id=ids[1]).delete()
    db.query(Subject).filter_by(id=ids[0]).delete()
    db.commit()
    db.close()


def _chunks(db, **filters):
    return db.query(KnowledgeChunk).filter_by(**filters).all()


# ---- chunking ---------------------------------------------------------


def test_chunk_text_keeps_a_short_section_whole():
    text = "Scheduling\nThe scheduler picks the next process to run on the CPU."
    assert chunk_text(text) == [
        "Scheduling The scheduler picks the next process to run on the CPU."
    ]


def test_chunk_text_windows_long_text_with_overlap():
    words = [f"w{i}" for i in range(1200)]
    chunks = chunk_text(" ".join(words), chunk_size=500, overlap=100)

    assert [len(c.split()) for c in chunks] == [500, 500, 400, 0 + 0][: len(chunks)]
    assert chunks[0].split()[400:500] == chunks[1].split()[:100]
    assert chunks[0].split()[0] == "w0"


def test_chunk_text_skips_title_only_sections_and_blank_input():
    assert chunk_text("   \n  ") == []
    assert chunk_text("COMPUTER NETWORKS") == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"chunk_size": 0},
        {"overlap": -1},
        {"chunk_size": 10, "overlap": 10},
    ],
)
def test_chunk_text_rejects_bad_parameters(kwargs):
    with pytest.raises(ValueError):
        chunk_text("some text here", **kwargs)


def test_split_into_sections_breaks_on_short_heading_lines():
    text = (
        "Intro\nThis opening paragraph explains the idea in a full sentence.\n"
        "Details\nThese details follow after the heading line, in a sentence."
    )
    sections = split_into_sections(text)

    assert len(sections) == 2
    assert sections[0].startswith("Intro")
    assert sections[1].startswith("Details")
    assert split_into_sections("") == []


# ---- concept ingestion ------------------------------------------------


BODY = "Processes\nA process is a program in execution with its own state and resources."


def test_ingest_for_concept_stores_embedded_chunks(curriculum, fake_embeddings):
    _, concept_id = curriculum
    db = SessionLocal()

    assert ingest_text_for_concept(db, concept_id, BODY, "notes.txt") == 1

    rows = _chunks(db, concept_id=concept_id)
    db.close()
    assert len(rows) == 1
    assert rows[0].source == "notes.txt"
    assert rows[0].subject_id is None
    assert len(rows[0].embedding) == 768
    assert len(fake_embeddings) == 1


def test_ingest_for_concept_skips_duplicates(curriculum, fake_embeddings):
    _, concept_id = curriculum
    db = SessionLocal()

    ingest_text_for_concept(db, concept_id, BODY, "notes.txt")
    assert ingest_text_for_concept(db, concept_id, BODY, "notes.txt") == 0

    assert len(_chunks(db, concept_id=concept_id)) == 1
    assert len(fake_embeddings) == 1  # the duplicate was never re-embedded
    db.close()


def test_ingest_for_concept_can_replace_a_source(curriculum):
    _, concept_id = curriculum
    db = SessionLocal()

    ingest_text_for_concept(db, concept_id, BODY, "notes.txt")
    new_body = "Threads\nA thread is the smallest unit of CPU scheduling inside a process."
    ingest_text_for_concept(db, concept_id, new_body, "notes.txt", replace_source=True)

    contents = [c.content for c in _chunks(db, concept_id=concept_id)]
    db.close()
    assert len(contents) == 1
    assert "thread" in contents[0].lower()


@pytest.mark.parametrize(
    "text,source,message",
    [
        ("   ", "s", "empty"),
        (BODY, "  ", "empty"),
        ("TITLE", "s", "No valid knowledge chunks"),
    ],
)
def test_ingest_for_concept_validates_input(curriculum, text, source, message):
    _, concept_id = curriculum
    db = SessionLocal()
    with pytest.raises(ValueError, match=message):
        ingest_text_for_concept(db, concept_id, text, source)
    db.close()


def test_ingest_for_concept_rejects_unknown_concept():
    db = SessionLocal()
    with pytest.raises(ValueError, match="does not exist"):
        ingest_text_for_concept(db, 10**9, BODY, "s")
    db.close()


def test_embedding_failure_rolls_back_the_whole_ingest(curriculum, monkeypatch):
    _, concept_id = curriculum
    body = BODY + "\nQueues\nA ready queue holds processes waiting for the CPU to run."

    state = {"n": 0}

    def flaky(text):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("ollama down")
        return FAKE_VECTOR

    monkeypatch.setattr(knowledge_ingestion, "generate_embedding", flaky)
    db = SessionLocal()

    with pytest.raises(RuntimeError):
        ingest_text_for_concept(db, concept_id, body, "notes.txt")

    assert _chunks(db, concept_id=concept_id) == []
    db.close()


# ---- subject ingestion ------------------------------------------------


def test_ingest_for_subject_stores_subject_level_chunks(curriculum):
    subject_id, _ = curriculum
    db = SessionLocal()

    assert ingest_text_for_subject(db, subject_id, BODY, "doc.pdf") == 1

    row = _chunks(db, subject_id=subject_id)[0]
    assert row.concept_id is None
    db.close()


def test_ingest_for_subject_replace_source(curriculum):
    subject_id, _ = curriculum
    db = SessionLocal()
    ingest_text_for_subject(db, subject_id, BODY, "doc.pdf")
    ingest_text_for_subject(db, subject_id, BODY, "doc.pdf", replace_source=True)

    assert len(_chunks(db, subject_id=subject_id)) == 1
    db.close()


@pytest.mark.parametrize(
    "subject_id,text,source,message",
    [
        (10**9, BODY, "s", "does not exist"),
        (None, "", "s", "empty"),
        (None, BODY, "", "empty"),
    ],
)
def test_ingest_for_subject_validates_input(curriculum, subject_id, text, source, message):
    real_subject, _ = curriculum
    db = SessionLocal()
    with pytest.raises(ValueError, match=message):
        ingest_text_for_subject(db, subject_id or real_subject, text, source)
    db.close()


def test_subject_embedding_failure_rolls_back(curriculum, monkeypatch):
    subject_id, _ = curriculum

    def boom(text):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(knowledge_ingestion, "generate_embedding", boom)
    db = SessionLocal()
    with pytest.raises(RuntimeError):
        ingest_text_for_subject(db, subject_id, BODY, "doc.pdf")
    assert _chunks(db, subject_id=subject_id) == []
    db.close()


# ---- file extraction --------------------------------------------------


def test_extract_text_from_txt_and_markdown(tmp_path):
    for name in ("a.txt", "b.md", "c.markdown"):
        path = tmp_path / name
        path.write_text("  hello world  \n", encoding="utf-8")
        assert source_ingestion.extract_file_text(path) == "hello world"


def test_extract_rejects_unsupported_extension(tmp_path):
    path = tmp_path / "x.docx"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported file type"):
        source_ingestion.extract_file_text(path)


def _pdf_with_text(path, text):
    """A minimal one-page PDF whose page contains ``text``."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref,
    )
    path.write_bytes(out)


def test_extract_text_from_a_real_pdf(tmp_path):
    path = tmp_path / "lesson.pdf"
    _pdf_with_text(path, "Paging maps virtual pages to frames")

    assert "Paging maps virtual pages to frames" in source_ingestion.extract_file_text(path)


def test_ingest_file_for_concept_end_to_end(curriculum, tmp_path):
    _, concept_id = curriculum
    path = tmp_path / "notes.md"
    path.write_text(BODY, encoding="utf-8")
    db = SessionLocal()

    inserted = source_ingestion.ingest_file_for_concept(
        db, concept_id, str(path), source="my-notes"
    )

    assert inserted == 1
    assert _chunks(db, concept_id=concept_id)[0].source == "my-notes"
    db.close()


def test_ingest_file_defaults_source_to_filename(curriculum, tmp_path):
    _, concept_id = curriculum
    path = tmp_path / "defaults.txt"
    path.write_text(BODY, encoding="utf-8")
    db = SessionLocal()

    source_ingestion.ingest_file_for_concept(db, concept_id, str(path))

    assert _chunks(db, concept_id=concept_id)[0].source == "defaults.txt"
    db.close()


def test_ingest_file_errors(curriculum, tmp_path):
    _, concept_id = curriculum
    db = SessionLocal()

    with pytest.raises(ValueError, match="File not found"):
        source_ingestion.ingest_file_for_concept(db, concept_id, str(tmp_path / "no.txt"))

    with pytest.raises(ValueError, match="not a file"):
        source_ingestion.ingest_file_for_concept(db, concept_id, str(tmp_path))

    empty = tmp_path / "empty.txt"
    empty.write_text("   ", encoding="utf-8")
    with pytest.raises(ValueError, match="No text could be extracted"):
        source_ingestion.ingest_file_for_concept(db, concept_id, str(empty))

    db.close()


def test_missing_pypdf_gives_a_clear_error(monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def no_pypdf(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("no pypdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pypdf)

    with pytest.raises(RuntimeError, match="pypdf is not installed"):
        source_ingestion.extract_pdf_text(tmp_path / "x.pdf")


# ---- seed script ------------------------------------------------------


def test_seed_script_embeds_every_entry_and_inserts_them(monkeypatch, fake_embeddings, test_student):
    """Run inside a rolled-back transaction: the script deletes all chunks."""

    connection = engine.connect()
    outer = connection.begin()

    def scoped_session():
        return Session(bind=connection, join_transaction_mode="create_savepoint")

    monkeypatch.setattr(ingest, "SessionLocal", scoped_session)

    try:
        # The seed data refers to concept ids 1-6; add any that are missing
        # (rolled back with everything else).
        setup = Session(bind=connection)
        existing = {c.id for c in setup.query(Concept).all()}
        needed = {item["concept_id"] for item in ingest.KNOWLEDGE}
        for concept_id in sorted(needed - existing):
            setup.add(Concept(id=concept_id, subject_id=1, name=f"Seed {concept_id}"))
        setup.flush()

        ingest.ingest_knowledge()

        check = Session(bind=connection)
        assert check.query(KnowledgeChunk).count() == len(ingest.KNOWLEDGE)
        assert len(fake_embeddings) == len(ingest.KNOWLEDGE)
    finally:
        outer.rollback()
        connection.close()
