import json
import re

from app.tutor.tutor_service import generate_response


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
    print("\n===== TRUE/FALSE DEBUG =====")
    print("QUESTION:", repr(question))
    print("STUDENT ANSWER:", repr(student_answer))
    print("EXPECTED ANSWER:", repr(expected_answer))
    print("============================\n")
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

    response = generate_response(prompt).strip()

    print("\n===== RAW LLM CLAIM ANALYSIS =====")
    print(response)
    print("==================================\n")
    print("\n===== STUDENT ANSWER =====")
    print(student_answer)

    print("\n===== EXPECTED ANSWER =====")
    print(expected_answer)

    print("\n===== RAW LLM CLAIM ANALYSIS =====")
    print(response)
    print("==================================\n")

    analysis = _extract_json_object(response)

    print("\n===== EVALUATION CLAIMS =====")
    print(json.dumps(analysis, indent=2))
    print("=============================\n")

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

        if assessment not in {
            "supported",
            "contradicts_expected",
            "unrelated",
        }:
            continue

        normalized_claims.append(
            {
                "claim": claim,
                "assessment": assessment,
            }
        )

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

        misconception = contradictory_claims[0]["claim"]

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
    # 2. No contradiction + no meaningful understanding
    # ---------------------------------------------------------

    if not meaningful_claims:

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
