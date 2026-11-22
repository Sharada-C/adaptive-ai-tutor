"""Diagnostic generation with the LLM and retrieval mocked."""

import json
import uuid
from types import SimpleNamespace

import pytest

from app.db.database import SessionLocal
from app.models import Concept, ConceptMastery, Subject
from app.models.student import StudentProfile, User
from app.tutor import diagnostic_service as svc
from tests.conftest import ensure_account

CONCEPT = SimpleNamespace(id=7, subject_id=3, name="Paging", description="Memory paging")

GOOD = {
    "question": "Why does the OS use paging?",
    "expected_answer": "To map virtual pages to physical frames.",
    "evaluation_criteria": ["Mentions virtual pages", "Mentions frames"],
    "misconception_guidance": "Paging is not swapping.",
}


# ---- _extract_json_object ---------------------------------------------


def test_extract_plain_json():
    assert svc._extract_json_object(json.dumps(GOOD)) == GOOD


def test_extract_json_inside_markdown_fence_and_prose():
    wrapped = "Here you go:\n```json\n" + json.dumps(GOOD) + "\n```\nHope it helps."
    assert svc._extract_json_object(wrapped) == GOOD


def test_extract_labelled_format_fallback():
    text = (
        "QUESTION: Why page?\n"
        "EXPECTED ANSWER: To avoid fragmentation.\n"
        "EVALUATION CRITERIA:\n1. Mentions fragmentation\n- Mentions frames\n"
        "MISCONCEPTION GUIDANCE: Paging is not swapping."
    )
    parsed = svc._extract_json_object(text)

    assert parsed["question"] == "Why page?"
    assert parsed["expected_answer"] == "To avoid fragmentation."
    assert parsed["evaluation_criteria"] == ["Mentions fragmentation", "Mentions frames"]
    assert parsed["misconception_guidance"] == "Paging is not swapping."


@pytest.mark.parametrize("bad", ["", "   ", "no json here", "[1, 2, 3]"])
def test_extract_rejects_unusable_responses(bad):
    with pytest.raises(ValueError):
        svc._extract_json_object(bad)


# ---- generate_diagnostic_content --------------------------------------


def _llm(monkeypatch, payload):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return payload if isinstance(payload, str) else json.dumps(payload)

    monkeypatch.setattr(svc, "generate_response", fake)
    return seen


def test_content_is_parsed_and_prompt_carries_context(monkeypatch):
    seen = _llm(monkeypatch, GOOD)

    content = svc.generate_diagnostic_content(
        CONCEPT, "beginner", "Paging splits memory into fixed-size pages.", ["Old question?"]
    )

    assert content == GOOD
    assert "Paging splits memory" in seen["prompt"]
    assert "Old question?" in seen["prompt"]
    assert "beginner" in seen["prompt"]


def test_first_question_prompt_says_so(monkeypatch):
    seen = _llm(monkeypatch, GOOD)
    svc.generate_diagnostic_content(CONCEPT, "beginner", "text")
    assert "first question" in seen["prompt"]


@pytest.mark.parametrize(
    "change,message",
    [
        ({"question": "  "}, "question was empty"),
        ({"expected_answer": ""}, "expected answer was empty"),
        ({"evaluation_criteria": []}, "No evaluation criteria"),
        ({"evaluation_criteria": "not a list"}, "No evaluation criteria"),
        ({"evaluation_criteria": ["", "  "]}, "No evaluation criteria"),
    ],
)
def test_content_validation(monkeypatch, change, message):
    _llm(monkeypatch, {**GOOD, **change})

    with pytest.raises(ValueError, match=message):
        svc.generate_diagnostic_content(CONCEPT, "beginner", "text")


# ---- retrieval ---------------------------------------------------------


def test_retrieval_joins_chunks(monkeypatch):
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return [
            {"chunk": SimpleNamespace(content="one")},
            {"chunk": SimpleNamespace(content="two")},
        ]

    monkeypatch.setattr(svc, "retrieve_with_subject_fallback", fake)

    assert svc.retrieve_diagnostic_knowledge(None, CONCEPT) == "one\n\ntwo"
    assert captured["concept_id"] == 7
    assert captured["subject_id"] == 3


def test_retrieval_without_material_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(svc, "retrieve_with_subject_fallback", lambda **kw: [])

    with pytest.raises(ValueError, match="No study material is available for 'Paging'"):
        svc.retrieve_diagnostic_knowledge(None, CONCEPT)


# ---- concept selection and the full diagnostic --------------------------


@pytest.fixture
def subject_with_concepts():
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    subject = Subject(name=f"Diag {tag}", description="t")
    db.add(subject)
    db.flush()
    concepts = [
        Concept(subject_id=subject.id, name=f"C{i}", description="d") for i in range(4)
    ]
    db.add_all(concepts)
    username = f"diag_{tag}"
    ensure_account(username)
    user = db.query(User).filter_by(username=username).one()
    student = StudentProfile(user_id=user.id, learning_level="beginner")
    db.add(student)
    db.commit()

    yield SimpleNamespace(
        subject_id=subject.id,
        concept_ids=[c.id for c in concepts],
        student_id=student.id,
        level=student.learning_level,
    )

    db.rollback()
    db.query(ConceptMastery).filter_by(student_id=student.id).delete()
    db.delete(student)
    db.delete(user)
    db.query(Concept).filter_by(subject_id=subject.id).delete()
    db.delete(subject)
    db.commit()
    db.close()


def _master(ctx, concept_id, score):
    db = SessionLocal()
    db.add(
        ConceptMastery(
            student_id=ctx.student_id,
            concept_id=concept_id,
            mastery_score=score,
            attempts=1,
            correct_answers=1,
        )
    )
    db.commit()
    db.close()


def test_selection_prefers_unmastered_concepts_then_fills_with_mastered(subject_with_concepts):
    ctx = subject_with_concepts
    _master(ctx, ctx.concept_ids[0], 0.95)  # mastered
    db = SessionLocal()

    picked = svc.select_diagnostic_concepts(db, ctx.student_id, ctx.subject_id, limit=3)
    assert [c.id for c in picked] == ctx.concept_ids[1:4]

    picked = svc.select_diagnostic_concepts(db, ctx.student_id, ctx.subject_id, limit=4)
    assert [c.id for c in picked] == ctx.concept_ids[1:4] + [ctx.concept_ids[0]]

    assert svc.select_diagnostic_concepts(db, ctx.student_id, ctx.subject_id, limit=0) == []
    assert svc.select_diagnostic_concepts(db, ctx.student_id, 10**9) == []
    db.close()


def test_full_diagnostic_passes_earlier_questions_forward(monkeypatch, subject_with_concepts):
    ctx = subject_with_concepts
    monkeypatch.setattr(
        svc, "retrieve_with_subject_fallback",
        lambda **kw: [{"chunk": SimpleNamespace(content="evidence")}],
    )
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        n = len(prompts)
        return json.dumps({**GOOD, "question": f"Question number {n}?"})

    monkeypatch.setattr(svc, "generate_response", fake)
    db = SessionLocal()

    questions = svc.generate_diagnostic(db, ctx.student_id, ctx.subject_id, ctx.level, limit=3)
    db.close()

    assert [q["question"] for q in questions] == [
        "Question number 1?", "Question number 2?", "Question number 3?"
    ]
    assert [q["concept_id"] for q in questions] == ctx.concept_ids[:3]
    assert "Question number 1?" in prompts[1]
    assert "Question number 2?" in prompts[2]
    assert "Question number 1?" not in prompts[0]


def test_diagnostic_limit_is_validated_and_capped(monkeypatch, subject_with_concepts):
    ctx = subject_with_concepts
    db = SessionLocal()

    with pytest.raises(ValueError, match="at least 1"):
        svc.generate_diagnostic(db, ctx.student_id, ctx.subject_id, ctx.level, limit=0)

    assert svc.generate_diagnostic(db, ctx.student_id, 10**9, ctx.level, limit=5) == []

    seen = {}

    def spy(db, student_id, subject_id, limit):
        seen["limit"] = limit
        return []

    monkeypatch.setattr(svc, "select_diagnostic_concepts", spy)
    svc.generate_diagnostic(db, ctx.student_id, ctx.subject_id, ctx.level, limit=500)
    db.close()

    assert seen["limit"] == 20
