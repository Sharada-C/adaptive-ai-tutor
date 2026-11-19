"""The evaluator must not score the student on claims they never made."""

import json

import pytest

from app.tutor import evaluation_service
from app.tutor.evaluation_service import (
    _evidence_is_in_answer,
    evaluate_answer,
)


QUESTION = "What is the purpose of a logical schema?"
EXPECTED = "It describes what data is stored and how it is related."
STUDENT = "It describes the logical structure of the data and its relationships."


def _llm_returns(monkeypatch, claims):
    monkeypatch.setattr(
        evaluation_service,
        "generate_response",
        lambda prompt: json.dumps({"claims": claims}),
    )


def _evaluate(student_answer=STUDENT):
    return evaluate_answer(
        question=QUESTION,
        expected_answer=EXPECTED,
        student_answer=student_answer,
    )


def test_invented_contradiction_is_ignored(monkeypatch):
    # The model "claims" the student said something that is really a
    # restatement of the question. The quote is not in the answer.
    _llm_returns(
        monkeypatch,
        [
            {
                "claim": "The purpose of a logical schema is to ignore storage.",
                "evidence": "purpose of a logical schema is to ignore storage",
                "assessment": "contradicts_expected",
            },
            {
                "claim": "It describes the logical structure of the data.",
                "evidence": "describes the logical structure of the data",
                "assessment": "supported",
            },
        ],
    )

    result = _evaluate()

    assert result["result"] == "correct"
    assert result["score"] == 1.0
    assert result["misconception"] is None


def test_real_contradiction_is_still_reported(monkeypatch):
    answer = "A logical schema stores the physical files on disk."

    _llm_returns(
        monkeypatch,
        [
            {
                "claim": "A logical schema stores physical files.",
                "evidence": "A logical schema stores the physical files on disk",
                "assessment": "contradicts_expected",
            }
        ],
    )

    result = _evaluate(answer)

    assert result["result"] == "incorrect"
    assert result["score"] == 0.3
    assert "physical files" in result["misconception"]


def test_claims_without_evidence_behave_as_before(monkeypatch):
    _llm_returns(
        monkeypatch,
        [
            {
                "claim": "It describes the data.",
                "assessment": "supported",
            }
        ],
    )

    assert _evaluate()["result"] == "correct"


def test_only_invented_claims_gives_no_understanding(monkeypatch):
    _llm_returns(
        monkeypatch,
        [
            {
                "claim": "Something never said.",
                "evidence": "completely different words here",
                "assessment": "supported",
            }
        ],
    )

    result = _evaluate()

    assert result["result"] == "incorrect"
    assert result["score"] == 0.0


@pytest.mark.parametrize(
    "evidence, expected",
    [
        ("describes the logical structure", True),
        ("DESCRIBES, the logical   structure!", True),
        ("describes the logical structure of data", True),  # light paraphrase
        ("ignore storage entirely", False),
        ("", False),
    ],
)
def test_evidence_matching(evidence, expected):
    assert _evidence_is_in_answer(evidence, STUDENT) is expected
