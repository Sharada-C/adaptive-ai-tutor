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


VERIFIER_MARKER = "Reply with exactly one word"


def _llm_returns(monkeypatch, claims, verdict="CONFLICTS"):
    """Claim analysis returns ``claims``; the second-opinion check returns
    ``verdict`` (only asked when a contradiction was flagged)."""

    def fake(prompt):
        if VERIFIER_MARKER in prompt:
            return verdict
        return json.dumps({"claims": claims})

    monkeypatch.setattr(evaluation_service, "generate_response", fake)


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

    # An answer sharing nothing with the expected one: the invented claim
    # is dropped and the keyword fallback finds nothing either.
    result = _evaluate("I am not sure about that.")

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


# ---- a restated expected answer is not a contradiction ----------------

CELL_QUESTION = "What is the primary function of the cell wall in plant cells?"
CELL_EXPECTED = (
    "The primary function of the cell wall in plant cells is to provide "
    "structural support, rigidity, and mechanical protection while "
    "preventing the cell from bursting when water enters."
)


def test_claim_that_just_restates_the_expected_answer_is_not_a_contradiction(
    monkeypatch,
):
    # Seen with a 3B model: it labelled the correct fact itself as the
    # student's "contradicting" belief.
    _llm_returns(
        monkeypatch,
        [
            {
                "claim": CELL_EXPECTED,
                "evidence": "it gives the cell its shape and support",
                "assessment": "contradicts_expected",
            }
        ],
    )

    result = evaluate_answer(
        question=CELL_QUESTION,
        expected_answer=CELL_EXPECTED,
        student_answer="It gives the cell its shape and support.",
    )

    assert result["result"] == "correct"
    assert result["misconception"] is None


def test_contradiction_feedback_quotes_the_student_and_shows_the_expected_answer(
    monkeypatch,
):
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

    assert "stores the physical files on disk" in result["feedback"]
    assert EXPECTED in result["feedback"]


# ---- the model returns nothing usable: retry, then fall back ----------

CELL_ANSWER = (
    "The primary function of the cell wall in plant cells is to provide "
    "structural support, rigidity, and protection, giving the cell its "
    "fixed shape."
)


def _llm_sequence(monkeypatch, replies):
    """Each call returns the next reply (a claims list)."""

    calls = {"n": 0}

    def fake(prompt):
        reply = replies[min(calls["n"], len(replies) - 1)]
        calls["n"] += 1
        return json.dumps({"claims": reply})

    monkeypatch.setattr(evaluation_service, "generate_response", fake)
    return calls


def _grade_cell(answer=CELL_ANSWER):
    return evaluate_answer(
        question=CELL_QUESTION,
        expected_answer=CELL_EXPECTED,
        student_answer=answer,
    )


def test_empty_model_reply_is_retried_once(monkeypatch):
    calls = _llm_sequence(
        monkeypatch,
        [
            [],
            [
                {
                    "claim": "The cell wall provides structural support.",
                    "evidence": "provide structural support",
                    "assessment": "supported",
                }
            ],
        ],
    )

    result = _grade_cell()

    assert calls["n"] == 2
    assert result["result"] == "correct"


def test_correct_answer_is_not_zero_when_the_model_finds_no_claims(monkeypatch):
    # The reported bug: a correct answer got 0% because the small model
    # returned nothing usable (twice).
    _llm_sequence(monkeypatch, [[]])

    result = _grade_cell()

    assert result["result"] in {"correct", "partially_correct"}
    assert result["score"] >= 0.5


def test_unrelated_answer_still_scores_zero_without_model_claims(monkeypatch):
    _llm_sequence(monkeypatch, [[]])

    result = _grade_cell("It makes energy for the cell.")

    assert result["result"] == "incorrect"
    assert result["score"] == 0.0


def test_restating_only_the_question_does_not_pass_the_fallback(monkeypatch):
    _llm_sequence(monkeypatch, [[]])

    result = _grade_cell("The primary function of the cell wall in plant cells.")

    assert result["score"] == 0.0


def test_fallback_never_overrides_a_model_contradiction(monkeypatch):
    _llm_returns(
        monkeypatch,
        [
            {
                "claim": "The cell wall removes support.",
                "evidence": "rigidity",
                "assessment": "contradicts_expected",
            }
        ],
    )

    assert _grade_cell()["result"] == "incorrect"


# ---- a flagged contradiction must survive a second opinion ------------

CALVIN_QUESTION = (
    "What is the primary purpose of the Calvin cycle in the light-independent "
    "reactions of photosynthesis?"
)
CALVIN_EXPECTED = (
    "The Calvin cycle captures CO2 from the atmosphere and uses the newly "
    "formed NADPH and ATP to produce three-carbon sugars, which are later "
    "combined to form sucrose and starch."
)
CALVIN_ANSWER = (
    "to use the chemical energy from ATP and NADPH to convert atmospheric "
    "carbon dioxide (CO2)"
)


def _calvin(monkeypatch, verifier_reply):
    """First model call: a (wrong) contradiction. Second: the verifier."""

    replies = iter(
        [
            json.dumps(
                {
                    "claims": [
                        {
                            "claim": "The primary purpose of the Calvin cycle is "
                            "to use the chemical energy from ATP and NADPH to "
                            "convert atmospheric carbon dioxide (CO2)",
                            "evidence": CALVIN_ANSWER,
                            "assessment": "contradicts_expected",
                        }
                    ]
                }
            ),
            verifier_reply,
        ]
    )
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        return next(replies)

    monkeypatch.setattr(evaluation_service, "generate_response", fake)
    return prompts


def _grade_calvin():
    return evaluate_answer(
        question=CALVIN_QUESTION,
        expected_answer=CALVIN_EXPECTED,
        student_answer=CALVIN_ANSWER,
    )


def test_contradiction_rejected_by_the_verifier_is_dropped(monkeypatch):
    prompts = _calvin(monkeypatch, "CONSISTENT")

    result = _grade_calvin()

    assert result["result"] == "correct"
    assert result["misconception"] is None
    # the verifier saw the student's own words and the reference, only
    assert CALVIN_ANSWER in prompts[1]
    assert CALVIN_EXPECTED in prompts[1]


def test_contradiction_confirmed_by_the_verifier_stands(monkeypatch):
    _calvin(monkeypatch, "CONFLICTS")

    result = _grade_calvin()

    assert result["result"] == "incorrect"
    assert result["score"] == 0.3


def test_unclear_verifier_reply_does_not_confirm_the_contradiction(monkeypatch):
    # Only an explicit CONFLICTS makes a contradiction stand. Otherwise the
    # answer is marked for review: partial credit, no stored misconception.
    _calvin(monkeypatch, "hmm, hard to say")

    result = _grade_calvin()

    assert result["result"] == "partially_correct"
    assert result["score"] == 0.5
    assert result["misconception"] is None
    assert CALVIN_EXPECTED in result["feedback"]


def test_failing_verifier_does_not_confirm_the_contradiction(monkeypatch):
    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        if VERIFIER_MARKER in prompt:
            raise ValueError("model offline")
        return json.dumps(
            {
                "claims": [
                    {
                        "claim": "x",
                        "evidence": CALVIN_ANSWER,
                        "assessment": "contradicts_expected",
                    }
                ]
            }
        )

    monkeypatch.setattr(evaluation_service, "generate_response", fake)

    result = _grade_calvin()

    assert result["result"] == "partially_correct"
    assert result["misconception"] is None


# ---- the grading model can differ from the tutor model ----------------


def test_grader_model_setting_is_used_for_grading_calls(monkeypatch):
    from app.core.config import settings

    seen = []

    def fake(prompt, model=None):
        seen.append(model)
        return json.dumps({"claims": []})

    monkeypatch.setattr(evaluation_service, "generate_response", fake)
    monkeypatch.setattr(settings, "grader_model", "qwen2.5:7b")

    _grade_cell()

    assert seen and set(seen) == {"qwen2.5:7b"}


def test_without_grader_model_the_default_model_is_used(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "grader_model", "")
    calls = []

    def fake(prompt):  # accepts no model argument at all
        calls.append(prompt)
        return json.dumps({"claims": []})

    monkeypatch.setattr(evaluation_service, "generate_response", fake)

    _grade_cell()

    assert calls


LATEX_REPLY = (
    '{"claims": [{"claim": "It converts CO\\(_2\\) into sugar", '
    '"evidence": "It converts CO\\(_2\\) into sugar", '
    '"assessment": "supported"}]}'
)


def test_json_with_latex_backslashes_still_parses():
    from app.tutor.evaluation_service import _extract_json_object

    parsed = _extract_json_object(LATEX_REPLY)

    assert parsed["claims"][0]["assessment"] == "supported"


def test_valid_json_escapes_are_left_alone():
    from app.tutor.evaluation_service import _extract_json_object

    parsed = _extract_json_object(r'{"a": "line\nbreak \"q\" \\ A"}')

    assert parsed["a"] == 'line\nbreak "q" \\ A'


def test_unparseable_model_reply_does_not_crash_grading(monkeypatch):
    monkeypatch.setattr(
        evaluation_service, "generate_response", lambda prompt: "no json here"
    )

    result = _evaluate()

    assert result["result"] in {"correct", "partially_correct", "incorrect"}
