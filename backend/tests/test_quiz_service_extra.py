"""Quiz generation: parsing repairs, validation and adaptive difficulty."""

import json

import pytest

from app.tutor import quiz_service

EVIDENCE = (
    "A process is a program in execution. The scheduler selects which ready "
    "process runs next on the CPU."
)

GOOD = {
    "question": "What does the scheduler select?",
    "expected_answer": "The scheduler selects which ready process runs next.",
    "difficulty": "medium",
}


def _quiz(monkeypatch, response, mastery=0.5, knowledge=EVIDENCE):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return response if isinstance(response, str) else json.dumps(response)

    monkeypatch.setattr(quiz_service, "generate_response", fake)
    result = quiz_service.generate_quiz(
        concept="Scheduling",
        concept_description="CPU scheduling",
        student_level="beginner",
        mastery_score=mastery,
        knowledge_text=knowledge,
        misconceptions=seen.get("m"),
    )
    return result, seen


def test_valid_quiz_is_returned(monkeypatch):
    result, _ = _quiz(monkeypatch, GOOD)
    assert result == GOOD


@pytest.mark.parametrize(
    "mastery,difficulty",
    [(0.0, "easy"), (0.39, "easy"), (0.4, "medium"), (0.7, "medium"), (0.71, "hard"), (1.0, "hard")],
)
def test_difficulty_follows_mastery(monkeypatch, mastery, difficulty):
    result, seen = _quiz(monkeypatch, {**GOOD, "difficulty": difficulty}, mastery=mastery)
    assert result["difficulty"] == difficulty
    assert f"Required difficulty:\n{difficulty}" in seen["prompt"]


def test_llm_ignoring_the_required_difficulty_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="expected 'easy'"):
        _quiz(monkeypatch, {**GOOD, "difficulty": "hard"}, mastery=0.1)


def test_markdown_fences_are_stripped(monkeypatch):
    result, _ = _quiz(monkeypatch, "```json\n" + json.dumps(GOOD) + "\n```")
    assert result == GOOD


def test_missing_closing_brace_is_repaired(monkeypatch):
    result, _ = _quiz(monkeypatch, json.dumps(GOOD)[:-1])
    assert result == GOOD


def test_json_surrounded_by_prose_is_extracted(monkeypatch):
    result, _ = _quiz(monkeypatch, "Sure! " + json.dumps(GOOD) + " Anything else?")
    assert result == GOOD


def test_unparseable_response_is_an_error(monkeypatch):
    with pytest.raises(ValueError, match="invalid JSON"):
        _quiz(monkeypatch, "I cannot do that.")


@pytest.mark.parametrize(
    "payload,message",
    [
        ({"question": "q?", "difficulty": "medium"}, "incomplete"),
        ({**GOOD, "question": "  "}, "empty question"),
        ({**GOOD, "expected_answer": ""}, "empty question or expected answer"),
        ({**GOOD, "difficulty": "impossible"}, "invalid difficulty"),
    ],
)
def test_response_validation(monkeypatch, payload, message):
    with pytest.raises(ValueError, match=message):
        _quiz(monkeypatch, payload)


@pytest.mark.parametrize("knowledge", ["", "   ", "No retrieved knowledge available."])
def test_no_evidence_means_no_quiz(monkeypatch, knowledge):
    with pytest.raises(ValueError, match="without retrieved knowledge"):
        _quiz(monkeypatch, GOOD, knowledge=knowledge)


def test_misconceptions_are_included_in_the_prompt(monkeypatch):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return json.dumps(GOOD)

    monkeypatch.setattr(quiz_service, "generate_response", fake)
    quiz_service.generate_quiz(
        "Scheduling", "d", "beginner", 0.5, EVIDENCE,
        misconceptions=["Thinks the scheduler is a process"],
    )

    assert "- Thinks the scheduler is a process" in seen["prompt"]
