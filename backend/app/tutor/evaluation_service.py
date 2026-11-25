import json
import logging
import re

from app.core.config import settings
from app.tutor.tutor_service import generate_response

logger = logging.getLogger(__name__)


PLACEHOLDER_MISCONCEPTIONS = {
    "",
    "string",
    "null",
    "none",
    "no misconception",
    "no misconception detected",
}


def _extract_json_object(response: str) -> dict:
    """
    Extract the first valid JSON object from an LLM response.
    """

    response = response.strip()

    if not response:
        raise ValueError("LLM returned an empty response.")

    response = (
        response
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        parsed = json.loads(response)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()

    for match in re.finditer(r"\{", response):
        try:
            parsed, _ = decoder.raw_decode(
                response[match.start():]
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            continue

    raise ValueError(
        f"LLM returned invalid JSON: {response}"
    )


def _normalize_text(text: str) -> str:
    """Lowercase and reduce text to space-separated alphanumeric words."""

    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _evidence_is_in_answer(evidence: str, student_answer: str) -> bool:
    """
    Return True if the quoted evidence really comes from the student's
    answer.

    Small language models sometimes "find" a claim by restating the
    question or the expected answer and attributing it to the student.
    Requiring a quotation that exists in the student's answer rejects
    those invented claims. A small amount of paraphrase is tolerated.
    """

    evidence_text = _normalize_text(evidence)
    answer_text = _normalize_text(student_answer)

    if not evidence_text:
        return False

    if evidence_text in answer_text:
        return True

    evidence_words = evidence_text.split()
    answer_words = set(answer_text.split())

    present = sum(1 for word in evidence_words if word in answer_words)

    return present / len(evidence_words) >= 0.85


def _judge(prompt: str) -> str:
    """Call the grading model (``GRADER_MODEL``, else the tutor model)."""

    if settings.grader_model:
        return generate_response(prompt, model=settings.grader_model)

    return generate_response(prompt)


def _analyze_claims(
    prompt: str,
    student_answer: str,
    expected_answer: str,
) -> list[dict]:
    """One model call -> validated claims (invented ones dropped)."""

    response = _judge(prompt).strip()

    logger.debug("raw LLM claim analysis: %s", response)

    analysis = _extract_json_object(response)

    logger.debug("evaluation claims: %s", json.dumps(analysis))

    claims = analysis.get("claims", [])

    if not isinstance(claims, list):
        claims = []

    normalized_claims = []

    for claim_data in claims:

        if not isinstance(claim_data, dict):
            continue

        claim = str(
            claim_data.get("claim", "")
        ).strip()

        assessment = str(
            claim_data.get("assessment", "")
        ).strip().lower()

        if not claim:
            continue

        # Reject claims that are not traceable to the student's words.
        # (Older responses without an "evidence" field are still accepted.)
        evidence = claim_data.get("evidence")

        if evidence is not None and not _evidence_is_in_answer(
            str(evidence),
            student_answer,
        ):
            continue

        if assessment not in {
            "supported",
            "contradicts_expected",
            "unrelated",
        }:
            continue

        if assessment == "contradicts_expected" and _restates_expected(
            claim, expected_answer
        ):
            assessment = "supported"

        normalized_claims.append(
            {
                "claim": claim,
                "assessment": assessment,
                "evidence": str(evidence).strip() if evidence else "",
            }
        )

    return normalized_claims


_STOPWORDS = frozenset(
    "a an the of to in on for and or but is are was were be been being it its "
    "this that these those as at by with from into than then so such which "
    "who whom what when where while how why not no can could may might will "
    "would should has have had do does did their there they them he she his "
    "her you your i we our us".split()
)


def _stems(text: str) -> set[str]:
    """Content words reduced to 5-letter prefixes ("protection"~"protect")."""

    return {
        word[:5]
        for word in _normalize_text(text).split()
        if word not in _STOPWORDS and len(word) > 2
    }


def _keyword_recall(question: str, expected_answer: str, student_answer: str) -> float:
    """Share of the expected answer's own key words found in the answer.

    Words that already appear in the question are ignored, so an answer
    that merely repeats the question scores 0.
    """

    needed = _stems(expected_answer) - _stems(question)

    if not needed:
        return 0.0

    return len(needed & _stems(student_answer)) / len(needed)


def _second_opinion(
    question: str,
    expected_answer: str,
    statement: str,
) -> str:
    """Second opinion on a flagged contradiction: consistent / conflicts / unclear.

    The long claim-extraction prompt makes small models over-flag errors,
    so a flagged statement is checked with one simple question. Only an
    explicit answer counts; an unclear reply or a model failure is
    "unclear" and never confirms the contradiction.
    """

    prompt = f"""You are checking a student's statement against a reference answer.

QUESTION:
{question}

REFERENCE ANSWER:
{expected_answer}

STUDENT STATEMENT:
{statement}

Is the student statement consistent with the reference answer (same meaning,
possibly worded differently, less detailed, or with extra correct detail), or
does it say something that conflicts with it?

Reply with exactly one word: CONSISTENT or CONFLICTS."""

    try:
        reply = _judge(prompt).upper()
    except Exception as error:
        logger.warning("contradiction check failed: %s", error)
        return "unclear"

    words = set(re.findall(r"\b(CONSISTENT|CONFLICTS)\b", reply))

    if words == {"CONSISTENT"}:
        return "consistent"

    if words == {"CONFLICTS"}:
        return "conflicts"

    return "unclear"


def _restates_expected(claim: str, expected_answer: str) -> bool:
    """True if a long claim is essentially the expected answer itself.

    A statement that matches the reference answer cannot contradict it.
    Small models sometimes label the reference fact as the student's
    "contradicting" belief. Only long claims are checked (a one-word
    difference in a short sentence, "increases" vs "decreases", is a real
    contradiction).
    """

    claim_words = _normalize_text(claim).split()
    expected_words = _normalize_text(expected_answer).split()

    if len(claim_words) < 8 or not expected_words:
        return False

    shared = set(claim_words) & set(expected_words)
    union = set(claim_words) | set(expected_words)

    return len(shared) / len(union) >= 0.9


def evaluate_answer(
    question: str,
    expected_answer: str,
    student_answer: str,
    evaluation_criteria: list[str] | None = None,
) -> dict:
    """
    Evaluate a student's answer using topic-independent
    claim-level semantic analysis.

    The LLM identifies whether student claims are:
    - supported
    - contradicting the expected answer
    - unrelated

    Python then determines the final pedagogical result.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if not expected_answer.strip():
        raise ValueError("Expected answer cannot be empty.")

    if not student_answer.strip():
        return {
            "score": 0.0,
            "result": "incorrect",
            "feedback": "No answer was provided.",
            "misconception": None,
        }
    # ---------------------------------------------------------
    # True/False questions
    # ---------------------------------------------------------
    question_lower = question.lower()
    logger.debug(
        "grading question=%r student_answer=%r expected_answer=%r",
        question,
        student_answer,
        expected_answer,
    )
    is_true_false = (
        "true or false" in question_lower
        or "is this statement true" in question_lower
        or "is this statement false" in question_lower
    )

    if is_true_false:
        student_value = student_answer.strip().lower()
        expected_value = expected_answer.strip().lower()

        if student_value in {"true", "false"} and expected_value in {
            "true",
            "false",
        }:
            if student_value == expected_value:
                return {
                    "score": 1.0,
                    "result": "correct",
                    "feedback": "The answer is correct.",
                    "misconception": None,
                }

            return {
                "score": 0.3,
                "result": "incorrect",
                "feedback": (
                    f"The correct answer is {expected_value}."
                ),
                "misconception": (
                    f"The student selected {student_value}, "
                    f"but the expected answer is {expected_value}."
                ),
            }
    criteria = evaluation_criteria or []

    criteria_text = "\n".join(
        f"- {criterion}"
        for criterion in criteria
    )

    if not criteria_text:
        criteria_text = (
            "No separate evaluation criteria are available. "
            "Use the expected answer as the reference."
        )

    prompt = f"""
You are a semantic claim analyzer for a general-purpose adaptive AI tutor.

Your job is NOT to decide the final score or final result.

Your ONLY job is to identify the meaningful claims made by the student
and compare those claims with the EXPECTED ANSWER.

Use only:

1. The question
2. The expected answer
3. The evaluation criteria
4. The student's answer

Do not assume a specific subject or domain.

Only report claims the student actually wrote. Every claim MUST include
"evidence": the exact words copied from the STUDENT ANSWER that express
it. Never create a claim from the question, the expected answer or the
evaluation criteria. If the student's answer is short or says little,
report few claims or none.

============================================================
QUESTION
============================================================

{question}

============================================================
EXPECTED ANSWER
============================================================

{expected_answer}

============================================================
EVALUATION CRITERIA
============================================================

{criteria_text}

============================================================
STUDENT ANSWER
============================================================

{student_answer}

============================================================
CLAIM ANALYSIS
============================================================

Extract the important conceptual claims made by the student.

For every meaningful claim, classify it as exactly one of:

"supported"
    The claim is consistent with the expected answer.

"contradicts_expected"
    The claim expresses a belief that conflicts with the expected answer.

"unrelated"
    The claim does not help answer the question.

IMPORTANT:

If the student says something that reverses, changes, or contradicts
a central relationship, definition, property, process, cause, effect,
or other important idea in the expected answer, classify that claim
as "contradicts_expected".

Do not reinterpret an incorrect claim as merely missing information.

For example:

Expected:
"A is an executing version of B."

Student:
"A is a stored version of B."

The student's claim contradicts the expected answer.

Another example:

Expected:
"X increases Y."

Student:
"X decreases Y."

The student's claim contradicts the expected answer.

Missing information is different.

If the student's answer is consistent with the expected answer but
does not mention an important requirement, do NOT create a
contradictory claim. Simply omit that claim from the student's
claims.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
  "claims": [
    {{
      "claim": "student's conceptual claim",
      "evidence": "the exact words copied from the STUDENT ANSWER",
      "assessment": "supported"
    }}
  ]
}}

Allowed assessment values:

"supported"
"contradicts_expected"
"unrelated"

Do not include score.
Do not include result.
Do not include feedback.
Do not include misconception.

Return ONLY the JSON object.
"""

    normalized_claims = _analyze_claims(prompt, student_answer, expected_answer)

    # Small local models sometimes return no usable claims at all. The
    # output is not deterministic, so one more attempt is worthwhile.
    if not any(c["assessment"] != "unrelated" for c in normalized_claims):
        normalized_claims = _analyze_claims(
            prompt, student_answer, expected_answer
        )

    # A flagged contradiction only stands if a second, simpler check agrees.
    for item in normalized_claims:
        if item["assessment"] != "contradicts_expected":
            continue

        verdict = _second_opinion(
            question,
            expected_answer,
            item["evidence"] or item["claim"],
        )

        if verdict == "consistent":
            item["assessment"] = "supported"
        elif verdict == "unclear":
            item["assessment"] = "unconfirmed"

    contradictory_claims = [
        item
        for item in normalized_claims
        if item["assessment"] == "contradicts_expected"
    ]

    supported_claims = [
        item
        for item in normalized_claims
        if item["assessment"] == "supported"
    ]

    meaningful_claims = [
        item
        for item in normalized_claims
        if item["assessment"] != "unrelated"
    ]

    # ---------------------------------------------------------
    # 1. Conceptual contradiction takes priority
    # ---------------------------------------------------------

    if contradictory_claims:

        first = contradictory_claims[0]
        misconception = first["claim"]

        if first["evidence"]:
            feedback = (
                f'You wrote "{first["evidence"]}", which conflicts with '
                f"the expected answer: {expected_answer.strip()}"
            )
        else:
            feedback = (
                "The answer contains a conceptual error: "
                f"{misconception}"
            )

        return {
            "score": 0.3,
            "result": "incorrect",
            "feedback": feedback,
            "misconception": (
                "The student expressed the following incorrect "
                f"belief: {misconception}"
            ),
        }

    # ---------------------------------------------------------
    # 1b. Flagged but not confirmed: mark for review, never record a
    #     misconception (it may be the model's mistake).
    # ---------------------------------------------------------

    unconfirmed_claims = [
        item
        for item in normalized_claims
        if item["assessment"] == "unconfirmed"
    ]

    if unconfirmed_claims:
        quoted = unconfirmed_claims[0]["evidence"]
        subject = f'"{quoted}"' if quoted else "part of your answer"

        return {
            "score": 0.5,
            "result": "partially_correct",
            "feedback": (
                f"{subject[0].upper() + subject[1:]} may not match the "
                f"expected answer: {expected_answer.strip()}"
            ),
            "misconception": None,
        }

    # ---------------------------------------------------------
    # 2. No contradiction + no meaningful understanding
    # ---------------------------------------------------------

    if not meaningful_claims:

        # The model gave nothing usable (twice). Do not punish the
        # student for that: fall back to a conservative keyword check
        # against the expected answer.
        recall = _keyword_recall(question, expected_answer, student_answer)

        if recall >= 0.5:
            return {
                "score": 1.0,
                "result": "correct",
                "feedback": (
                    "The answer covers the key points of the expected answer."
                ),
                "misconception": None,
            }

        if recall >= 0.25:
            return {
                "score": 0.5,
                "result": "partially_correct",
                "feedback": (
                    "The answer covers some key points of the expected "
                    "answer but not all of them."
                ),
                "misconception": None,
            }

        return {
            "score": 0.0,
            "result": "incorrect",
            "feedback": (
                "The answer does not demonstrate the required "
                "understanding."
            ),
            "misconception": None,
        }

    # ---------------------------------------------------------
    # 3. Supported claims only
    # ---------------------------------------------------------

    if supported_claims:
        return {
            "score": 1.0,
            "result": "correct",
            "feedback": (
                "The answer demonstrates the required understanding."
            ),
            "misconception": None,
    }
