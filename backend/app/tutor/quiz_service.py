import json

from app.tutor.tutor_service import generate_response


def generate_quiz(
    concept: str,
    concept_description: str | None,
    student_level: str,
    mastery_score: float,
    knowledge_text: str = "No retrieved knowledge available.",
    misconceptions: list[str] | None = None,
) -> dict:

    misconceptions = misconceptions or []

    if misconceptions:
        misconception_text = "\n".join(
            f"- {item}"
            for item in misconceptions
        )
    else:
        misconception_text = "None"

    # Determine expected difficulty outside the LLM.
    if mastery_score < 0.4:
        expected_difficulty = "easy"
    elif mastery_score <= 0.7:
        expected_difficulty = "medium"
    else:
        expected_difficulty = "hard"

    prompt = f"""
You are an adaptive academic tutor generating ONE assessment question.

STUDENT CONTEXT
---------------
Student level:
{student_level}

Current mastery:
{mastery_score}

Required difficulty:
{expected_difficulty}

CONCEPT
-------
{concept}

Concept description:
{concept_description}

ACTIVE MISCONCEPTIONS
---------------------
{misconception_text}

RETRIEVED KNOWLEDGE
-------------------
{knowledge_text}

GROUNDING RULES
---------------
- Use the retrieved knowledge as the primary factual source.
- Test only the specified concept.
- Do not introduce facts unsupported by the retrieved knowledge.
- Do not test unrelated concepts.
- The question must be answerable using the retrieved knowledge.
- The expected answer must be supported by the retrieved knowledge.
- Do not invent facts to make the question harder.
- If an active misconception exists, test whether the student
  actually understands the misconception.
- Do not state the correct answer inside the question.

QUESTION GENERATION RULES
--------------------------
- Generate exactly ONE question.
- Test conceptual understanding.
- Prefer a clear conceptual question over an incidental detail.
- Avoid ambiguous wording.
- Avoid questions whose answer depends on information
  not present in the retrieved knowledge.
- Match the student's level.
- Use the required difficulty exactly:
- Prefer questions that require the student to explain, identify,
  apply, or reason about the concept.
- Do not ask questions where the answer is simply the name of a
  scheduling algorithm unless the concept being tested is specifically
  that algorithm.
- Do not make the question circular, such as asking which algorithm
  is used in a policy whose name already identifies the algorithm.
Required difficulty:
{expected_difficulty}

Difficulty meanings:
- easy: basic conceptual understanding
- medium: application or explanation of the concept
- hard: deeper reasoning or comparison within the concept

EXPECTED ANSWER RULES
---------------------
- Give a concise correct answer.
- Directly answer the question.
- Use only information supported by the retrieved knowledge.
- Do not include unrelated information.

Return ONLY valid JSON.

Required format:

{{
  "question": "the question",
  "expected_answer": "a concise correct answer",
  "difficulty": "{expected_difficulty}"
}}

Return JSON only.
"""

    response = generate_response(prompt).strip()

    # Remove accidental markdown code fences.
    if response.startswith("```"):
        response = response.replace("```json", "")
        response = response.replace("```", "")
        response = response.strip()

    try:
        result = json.loads(response)
    except json.JSONDecodeError as error:
        raise ValueError(
            "LLM returned invalid JSON for quiz generation."
        ) from error

    # Validate required fields.
    required_fields = {
        "question",
        "expected_answer",
        "difficulty",
    }

    if not required_fields.issubset(result):
        raise ValueError(
            "LLM returned an incomplete quiz response."
        )

    # Validate field types.
    if not isinstance(result["question"], str):
        raise ValueError(
            "LLM returned an invalid question."
        )

    if not isinstance(result["expected_answer"], str):
        raise ValueError(
            "LLM returned an invalid expected answer."
        )

    # Validate difficulty.
    if result["difficulty"] not in {
        "easy",
        "medium",
        "hard",
    }:
        raise ValueError(
            "LLM returned an invalid difficulty."
        )

    # Prevent the LLM from ignoring our adaptive difficulty decision.
    if result["difficulty"] != expected_difficulty:
        raise ValueError(
            f"LLM returned difficulty "
            f"'{result['difficulty']}', "
            f"but expected '{expected_difficulty}'."
        )

    return result