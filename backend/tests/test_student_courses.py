"""Students can create their own private course on any topic."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import curriculum as curriculum_api
from app.core.config import settings
from app.db.database import SessionLocal
from app.main import app
from app.models import Concept, Subject
from app.models.knowledge import KnowledgeChunk
from app.models.student import StudentProfile, User
from app.rag import knowledge_ingestion
from app.services import web_material
from app.services.web_material import Article
from tests.conftest import ensure_account, token_for

client = TestClient(app)

FAKE_VECTOR = [0.01] * 768
ARTICLE_TEXT = " ".join(["Binary search halves the sorted range at every step."] * 12)


def _curriculum_for(topic):
    return {
        "subject": topic,
        "description": f"A course on {topic}.",
        "concepts": [
            {"name": "Basics", "description": "The basics", "prerequisites": []},
            {"name": "Advanced", "description": "More", "prerequisites": ["Basics"]},
        ],
    }


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No Ollama, no internet: stubs for the LLM, embeddings and Wikipedia."""
    monkeypatch.setattr(curriculum_api, "generate_curriculum", _curriculum_for)
    monkeypatch.setattr(knowledge_ingestion, "generate_embedding", lambda t: FAKE_VECTOR)
    monkeypatch.setattr(
        curriculum_api,
        "collect_material",
        lambda topic, concept_names: [
            Article("Binary search", "https://en.wikipedia.org/wiki/Binary_search", ARTICLE_TEXT)
        ],
    )


@pytest.fixture
def people():
    """Two ordinary students, plus cleanup of everything they create."""
    tag = uuid.uuid4().hex[:8]
    db = SessionLocal()
    made = {}
    for key in ("a", "b"):
        name = f"sc_{key}_{tag}"
        ensure_account(name)
        user = db.query(User).filter_by(username=name).one()
        profile = StudentProfile(user_id=user.id, learning_level="beginner")
        db.add(profile)
        db.commit()
        made[key] = {
            "user_id": user.id,
            "student_id": profile.id,
            "headers": token_for(name),
        }
    db.close()
    made["tag"] = tag

    yield made

    db = SessionLocal()
    subjects = db.query(Subject).filter(
        Subject.owner_id.in_([made["a"]["user_id"], made["b"]["user_id"]])
    ).all()
    ids = [s.id for s in subjects]
    db.query(KnowledgeChunk).filter(KnowledgeChunk.subject_id.in_(ids)).delete(
        synchronize_session=False
    )
    for concept in db.query(Concept).filter(Concept.subject_id.in_(ids)).all():
        concept.prerequisites.clear()
    db.flush()
    db.query(Concept).filter(Concept.subject_id.in_(ids)).delete(synchronize_session=False)
    db.query(Subject).filter(Subject.id.in_(ids)).delete(synchronize_session=False)
    for key in ("a", "b"):
        db.query(StudentProfile).filter_by(id=made[key]["student_id"]).delete()
        db.query(User).filter_by(id=made[key]["user_id"]).delete()
    db.commit()
    db.close()


def _create(headers, topic):
    return client.post("/subjects/from-topic", headers=headers, json={"topic": topic})


def test_student_creates_a_private_course_with_material(people):
    topic = f"Binary Search {people['tag']}"

    response = _create(people["a"]["headers"], topic)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] is True
    assert body["concepts_created"] == 2
    assert body["material"]["articles"] == ["Binary search"]
    assert body["material"]["chunks"] >= 1
    assert body["needs_material"] is False

    db = SessionLocal()
    subject = db.get(Subject, body["subject_id"])
    assert subject.owner_id == people["a"]["user_id"]
    chunks = db.query(KnowledgeChunk).filter_by(subject_id=subject.id).all()
    assert chunks and all(c.source.startswith("Wikipedia: Binary search") for c in chunks)
    assert "en.wikipedia.org/wiki/Binary_search" in chunks[0].source
    db.close()


def test_other_students_cannot_see_or_use_a_private_course(people):
    topic = f"Secret Topic {people['tag']}"
    subject_id = _create(people["a"]["headers"], topic).json()["subject_id"]
    b = people["b"]

    names = [s["name"] for s in client.get("/subjects", headers=b["headers"]).json()]
    assert topic not in names
    mine = [s["name"] for s in client.get("/subjects", headers=people["a"]["headers"]).json()]
    assert topic in mine

    assert client.get(f"/subjects/{subject_id}/concepts", headers=b["headers"]).status_code == 404
    assert client.get(
        f"/students/{b['student_id']}/subjects/{subject_id}/next", headers=b["headers"]
    ).status_code == 404
    assert client.post(
        "/diagnostic/start",
        headers=b["headers"],
        json={"student_id": b["student_id"], "subject_id": subject_id, "question_count": 2},
    ).status_code == 404

    db = SessionLocal()
    concept_id = db.query(Concept).filter_by(subject_id=subject_id).first().id
    db.close()
    for path in ("/tutor/lesson", "/tutor/quiz"):
        response = client.post(
            path, headers=b["headers"],
            json={"student_id": b["student_id"], "concept_id": concept_id},
        )
        assert response.status_code == 404, path


def test_owner_can_use_their_course(people):
    a = people["a"]
    subject_id = _create(a["headers"], f"Mine {people['tag']}").json()["subject_id"]

    assert client.get(f"/subjects/{subject_id}/concepts", headers=a["headers"]).status_code == 200
    plan = client.get(
        f"/students/{a['student_id']}/subjects/{subject_id}/next", headers=a["headers"]
    )
    assert plan.status_code == 200
    assert plan.json()["status"] == "next"


def test_two_students_can_have_the_same_topic(people):
    topic = f"Shared Name {people['tag']}"

    first = _create(people["a"]["headers"], topic)
    second = _create(people["b"]["headers"], topic)

    assert first.status_code == second.status_code == 201
    assert first.json()["subject_id"] != second.json()["subject_id"]


def test_asking_twice_returns_the_existing_course(people):
    topic = f"Again {people['tag']}"

    first = _create(people["a"]["headers"], topic).json()
    again = _create(people["a"]["headers"], topic)

    assert again.status_code == 200
    assert again.json()["subject_id"] == first["subject_id"]
    assert again.json()["created"] is False


def test_no_wikipedia_material_still_creates_the_course(people, monkeypatch):
    monkeypatch.setattr(curriculum_api, "collect_material", lambda topic, names: [])

    response = _create(people["a"]["headers"], f"Obscure {people['tag']}")

    assert response.status_code == 201
    body = response.json()
    assert body["needs_material"] is True
    assert body["material"]["chunks"] == 0
    assert "upload" in body["message"].lower()


def test_embedding_failure_keeps_the_course_and_asks_for_material(people, monkeypatch):
    def boom(text):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(knowledge_ingestion, "generate_embedding", boom)

    response = _create(people["a"]["headers"], f"Embed Fail {people['tag']}")

    assert response.status_code == 201
    assert response.json()["needs_material"] is True


@pytest.mark.parametrize("topic", ["", "  ", "ab", "x" * 101])
def test_topic_is_validated(people, topic):
    assert _create(people["a"]["headers"], topic).status_code in (400, 422)


def test_course_limit_per_user(people, monkeypatch):
    monkeypatch.setattr(settings, "max_courses_per_user", 2)
    a = people["a"]["headers"]

    assert _create(a, f"One {people['tag']}").status_code == 201
    assert _create(a, f"Two {people['tag']}").status_code == 201
    third = _create(a, f"Three {people['tag']}")

    assert third.status_code == 409
    assert "limit" in third.json()["detail"].lower()


def test_generation_failure_creates_nothing(people, monkeypatch):
    def fail(topic):
        raise ValueError("model returned junk")

    monkeypatch.setattr(curriculum_api, "generate_curriculum", fail)
    topic = f"Junk {people['tag']}"

    assert _create(people["a"]["headers"], topic).status_code == 400

    db = SessionLocal()
    assert db.query(Subject).filter_by(name=topic).count() == 0
    db.close()


def test_students_see_shared_courses_too(people):
    db = SessionLocal()
    shared = Subject(name=f"Shared Course {people['tag']}", description="s")
    db.add(shared)
    db.commit()
    shared_id = shared.id
    db.close()

    try:
        names = [s["name"] for s in client.get("/subjects", headers=people["b"]["headers"]).json()]
        assert f"Shared Course {people['tag']}" in names
        flags = {
            s["name"]: s["is_private"]
            for s in client.get("/subjects", headers=people["b"]["headers"]).json()
        }
        assert flags[f"Shared Course {people['tag']}"] is False
    finally:
        db = SessionLocal()
        db.query(Subject).filter_by(id=shared_id).delete()
        db.commit()
        db.close()


# ---- uploads to your own course --------------------------------------


def _upload(headers, subject_id):
    return client.post(
        "/knowledge/upload/subject",
        headers=headers,
        data={"subject_id": str(subject_id)},
        files={"file": ("notes.txt", b"Heaps keep the smallest item at the root. " * 20, "text/plain")},
    )


def test_student_can_upload_notes_to_their_own_course_only(people):
    a, b = people["a"], people["b"]
    own = _create(a["headers"], f"Upload Own {people['tag']}").json()["subject_id"]

    assert _upload(a["headers"], own).status_code == 201
    assert _upload(b["headers"], own).status_code in (403, 404)

    db = SessionLocal()
    shared = Subject(name=f"Upload Shared {people['tag']}", description="s")
    db.add(shared)
    db.commit()
    shared_id = shared.id
    db.close()
    try:
        assert _upload(a["headers"], shared_id).status_code == 403
    finally:
        db = SessionLocal()
        db.query(Subject).filter_by(id=shared_id).delete()
        db.commit()
        db.close()


# ---- the Wikipedia client ---------------------------------------------


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise web_material.requests.HTTPError(str(self.status_code))

    def json(self):
        return self.payload


def _wiki(monkeypatch, pages):
    """pages: {title: extract}. Serves the two Wikipedia calls the client makes."""
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append(params)
        assert "AdaptiveAITutor" in headers["User-Agent"]
        if params.get("list") == "search":
            hits = [{"title": t} for t in pages if params["srsearch"].lower().split()[0] in t.lower()
                    or True]
            return FakeResponse({"query": {"search": hits[: params["srlimit"]]}})
        title = params["titles"]
        return FakeResponse({"query": {"pages": {"1": {
            "title": title,
            "fullurl": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            "extract": pages[title],
        }}}})

    monkeypatch.setattr(web_material.requests, "get", fake_get)
    return calls


LONG = " ".join(f"word{i}" for i in range(500))


def test_collect_material_returns_cited_articles(monkeypatch):
    _wiki(monkeypatch, {"Binary search": LONG})

    articles = web_material.collect_material("binary search", ["Basics"])

    assert articles
    assert articles[0].title == "Binary search"
    assert articles[0].url == "https://en.wikipedia.org/wiki/Binary_search"
    assert len(articles) == len({a.title for a in articles})  # deduplicated


def test_disambiguation_and_stub_pages_are_skipped(monkeypatch):
    _wiki(monkeypatch, {
        "Mercury": "Mercury may refer to: " + LONG,
        "Tiny": "Too short.",
        "Good page": LONG,
    })

    titles = [a.title for a in web_material.collect_material("x", [])]

    assert titles == ["Good page"]


def test_article_text_is_capped(monkeypatch):
    monkeypatch.setattr(settings, "web_material_max_words", 100)
    _wiki(monkeypatch, {"Long": " ".join(f"w{i}" for i in range(5000))})

    article = web_material.collect_material("long", [])[0]

    assert len(article.text.split()) == 100


def test_network_errors_give_no_material_instead_of_crashing(monkeypatch):
    def down(url, params, headers, timeout):
        raise web_material.requests.ConnectionError("offline")

    monkeypatch.setattr(web_material.requests, "get", down)

    assert web_material.collect_material("anything", ["a", "b"]) == []


def test_web_material_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "web_material_enabled", False)
    calls = _wiki(monkeypatch, {"Binary search": LONG})

    assert web_material.collect_material("binary search", []) == []
    assert calls == []
