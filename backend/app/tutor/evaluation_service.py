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

    # First try parsing the complete response.
    try:
        parsed = json.loads(response)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Otherwise, find the first valid JSON object.
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
    semantic evaluation.

    The evaluator does not contain subject-specific rules.
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

    criteria = evaluation_criteria or []

    criteria_text = "\n".join(
        f"- {criterion}"
        for criterion in criteria
    )

    if not criteria_text:
        criteria_text = (
            "No separate evaluation criteria are available. "
            "Evaluate the expected answer directly."
        )

    prompt = f"""
You are a semantic evaluator for a general-purpose adaptive AI tutor.

Your task is to evaluate a student's ACTUAL conceptual understanding.

You must evaluate the student's answer using only:

1. The question
2. The expected answer
3. The evaluation criteria
4. The student's answer

Do not assume a specific subject, domain, curriculum, or educational
framework beyond the information provided.

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
GENERAL EVALUATION PRINCIPLES
============================================================

1. Evaluate semantic meaning, not exact wording.

2. Accept answers that express the same understanding using different
   words, sentence structures, terminology, or level of detail.

3. Do not require the student to reproduce the expected answer
   word-for-word.

4. Do not penalize minor wording differences when the underlying
   concept is correct.

5. Do not require information that is not necessary to answer the
   question or satisfy the evaluation criteria.

6. Evaluate the student's actual answer rather than what the student
   might have intended to say.

7. Do not introduce outside knowledge when deciding whether the
   answer satisfies the provided criteria.

============================================================
CORRECT
============================================================

Use "correct" when the student demonstrates the core understanding
required by the question.

The student may use different wording from the expected answer.

The student does not need to mention every minor detail.

============================================================
PARTIALLY CORRECT
============================================================

Use "partially_correct" when the student demonstrates meaningful
understanding of some, but not all, important requirements of the
question.

Typical cases include:

- One important aspect is missing.
- The student explains only part of a multi-part answer.
- The student demonstrates the central idea but lacks an important
  supporting aspect.

Missing information is NOT automatically a misconception.

============================================================
INCORRECT
============================================================

Use "incorrect" when:

- The answer does not demonstrate the required understanding, or
- The answer contains a clear conceptual claim that conflicts with
  the expected answer or evaluation criteria.

A clearly incorrect conceptual claim should be classified as
"incorrect" even if the answer contains some vague or generally
relevant statements.

============================================================
MISCONCEPTION DETECTION
============================================================

A misconception is a specific false conceptual belief expressed
or clearly implied by the student's answer.

Only report a misconception when there is actual evidence of an
incorrect belief in the student's answer.

Do NOT infer a misconception from:

- omission
- incomplete explanation
- short answers
- missing details
- failure to satisfy one criterion
- lack of examples
- lack of terminology

If the student simply fails to mention an important concept,
classify the answer as partially_correct when appropriate and set
misconception to null.

If the student explicitly states or clearly implies a belief that
contradicts the expected answer or evaluation criteria, classify the
answer as incorrect and describe that false belief.

The misconception must be based on the student's actual words.

Never invent a misconception.

============================================================
SCORE GUIDANCE
============================================================

Use a score between 0.0 and 1.0.

Use the following general interpretation:

1.0:
The required understanding is demonstrated.

Around 0.5:
Meaningful understanding is demonstrated, but one or more important
requirements are missing.

Around 0.0:
The required understanding is not demonstrated or the answer contains
a fundamental conceptual error.

The exact score may be adjusted based on how much of the required
understanding is demonstrated.

============================================================
FEEDBACK
============================================================

For a correct answer:
Briefly explain what the student demonstrated correctly.

For a partially correct answer:
State what the student understood and what important requirement was
not demonstrated.

For an incorrect answer:
Briefly explain the conceptual problem.

If a misconception is detected, explain the incorrect belief clearly
and concisely.

Do not introduce unrelated information.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY one valid JSON object.

The JSON must contain exactly these fields:

{{
  "score": 0.0,
  "result": "correct",
  "feedback": "Brief explanation.",
  "misconception": null
}}

Allowed result values:

"correct"
"partially_correct"
"incorrect"

The misconception field must be either:

null

or

"a concise description of the specific false conceptual belief
expressed by the student."

Do not include markdown.

Do not include code fences.

Do not include explanations outside the JSON.

Return ONLY the JSON object.
"""

    response = generate_response(prompt).strip()

    evaluation = _extract_json_object(response)

    # ---------------------------------------------------------
    # Validate score
    # ---------------------------------------------------------

    try:
        score = float(evaluation["score"])

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as error:

        raise ValueError(
            "LLM returned an invalid score."
        ) from error

    if not 0.0 <= score <= 1.0:
        raise ValueError(
            "LLM returned an invalid score."
        )

    # ---------------------------------------------------------
    # Validate result
    # ---------------------------------------------------------

    result = evaluation.get("result")

    allowed_results = {
        "correct",
        "partially_correct",
        "incorrect",
    }

    if result not in allowed_results:
        raise ValueError(
            "LLM returned an invalid result."
        )

    # ---------------------------------------------------------
    # Normalize misconception
    # ---------------------------------------------------------

    misconception = evaluation.get(
        "misconception"
    )

    if misconception is not None:

        misconception = str(
            misconception
        ).strip()

        if misconception.lower() in PLACEHOLDER_MISCONCEPTIONS:
            misconception = None

    # ---------------------------------------------------------
    # Correct answers cannot contain misconceptions.
    # ---------------------------------------------------------

    if result == "correct":

        score = 1.0
        misconception = None

    # ---------------------------------------------------------
    # Protect against LLM confusing omission with misconception.
    # ---------------------------------------------------------

    if misconception:

        misconception_lower = misconception.lower()

        omission_phrases = [
            "did not mention",
            "does not mention",
            "failed to mention",
            "without mentioning",
            "missing information",
            "missing detail",
            "omitted information",
            "omitted detail",
            "not mention",
            "has not demonstrated",
            "not demonstrated",
            "does not address",
            "did not address",
            "fails to address",
        ]

        if any(
            phrase in misconception_lower
            for phrase in omission_phrases
        ):

            misconception = None

            if result == "incorrect":
                result = "partially_correct"
                score = max(0.5, score)

    # ---------------------------------------------------------
    # Final normalized result
    # ---------------------------------------------------------

    evaluation["score"] = score
    evaluation["result"] = result
    evaluation["misconception"] = misconception

    return evaluation