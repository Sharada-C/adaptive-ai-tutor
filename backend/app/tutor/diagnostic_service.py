import json
import re

from sqlalchemy.orm import Session
from app.models.curriculum import Subject, Concept
from app.models.student import ConceptMastery
from app.tutor.evaluation_service import evaluate_answer

from app.rag.retriever import retrieve_relevant_chunks_with_scores
from app.tutor.tutor_service import generate_response


MASTERY_THRESHOLD = 0.80


def get_concept_mastery(
    db: Session,
    student_id: int,
    concept_id: int,
) -> float:
    mastery = (
        db.query(ConceptMastery)
        .filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == concept_id,
        )
        .first()
    )

    if not mastery:
        return 0.0

    return mastery.mastery_score


def select_diagnostic_concepts(
    db: Session,
    student_id: int,
    subject_id: int,
    limit: int = 5,
) -> list[Concept]:

    if limit < 1:
        return []

    concepts = (
        db.query(Concept)
        .filter(
            Concept.subject_id == subject_id,
        )
        .order_by(
            Concept.id,
        )
        .all()
    )

    if not concepts:
        return []

    # Prefer concepts with little or no mastery history.
    # If fewer than `limit` such concepts exist, fill the
    # remaining slots with the other concepts.
    unmastered = [
        concept
        for concept in concepts
        if get_concept_mastery(
            db=db,
            student_id=student_id,
            concept_id=concept.id,
        ) < MASTERY_THRESHOLD
    ]

    mastered_or_known = [
        concept
        for concept in concepts
        if concept not in unmastered
    ]

    candidates = unmastered + mastered_or_known

    return candidates[:limit]


def retrieve_diagnostic_knowledge(
    db: Session,
    concept: Concept,
) -> str:

    results = retrieve_relevant_chunks_with_scores(
        db=db,
        query=(
            f"{concept.name}. "
            f"{concept.description or ''}"
        ),
        concept_id=concept.id,
        limit=3,
    )

    if not results:
        raise ValueError(
            f"No knowledge available for diagnostic concept "
            f"'{concept.name}'."
        )

    return "\n\n".join(
        item["chunk"].content
        for item in results
    )


def _extract_json_object(response: str) -> dict:
    response = response.strip()

    if not response:
        raise ValueError("LLM returned an empty diagnostic response.")

    # Remove markdown fences if present
    response = response.replace("```json", "").replace("```", "").strip()

    # First try strict JSON
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting a JSON object from surrounding text
    decoder = json.JSONDecoder()

    for match in re.finditer(r"\{", response):
        try:
            parsed, _ = decoder.raw_decode(response[match.start():])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # Fallback: parse the structured labelled format produced by the LLM
    labels = [
        "QUESTION:",
        "EXPECTED ANSWER:",
        "EVALUATION CRITERIA:",
        "MISCONCEPTION GUIDANCE:",
    ]

    if all(label in response for label in labels):
        question = response.split("QUESTION:", 1)[1].split(
            "EXPECTED ANSWER:", 1
        )[0].strip()

        expected_answer = response.split("EXPECTED ANSWER:", 1)[1].split(
            "EVALUATION CRITERIA:", 1
        )[0].strip()

        criteria_text = response.split("EVALUATION CRITERIA:", 1)[1].split(
            "MISCONCEPTION GUIDANCE:", 1
        )[0].strip()

        misconception = response.split(
            "MISCONCEPTION GUIDANCE:", 1
        )[1].strip()

        criteria = []

        for line in criteria_text.splitlines():
            line = line.strip()

            # Accept:
            # 1. ...
            # 2. ...
            # - ...
            line = re.sub(r"^\s*(?:\d+[\.\)]|-)\s*", "", line)

            if line:
                criteria.append(line)

        return {
            "question": question,
            "expected_answer": expected_answer,
            "evaluation_criteria": criteria,
            "misconception_guidance": misconception,
        }

    raise ValueError(
        f"LLM returned invalid diagnostic JSON: {response}"
    )


def generate_diagnostic_content(
    concept: Concept,
    student_level: str,
    knowledge_text: str,
) -> dict:
    """
    Generate one topic-independent diagnostic item.

    The question, expected answer, evaluation criteria,
    and misconception guidance are all generated from
    retrieved knowledge.
    """

    prompt = f"""
You are designing ONE diagnostic assessment item for an
adaptive AI tutor.

STUDENT LEVEL:
{student_level}

CURRENT CONCEPT:
{concept.name}

CONCEPT DESCRIPTION:
{concept.description or "No description available."}

RETRIEVED KNOWLEDGE:
{knowledge_text}

============================================================
TASK
============================================================

Create ONE conceptual diagnostic question that assesses
understanding of the CURRENT CONCEPT.

Before creating the question, internally determine:

CORE CONCEPT SCOPE:
What is the central meaning of the CURRENT CONCEPT according
to the RETRIEVED KNOWLEDGE?

Use this internal scope to ensure that the question assesses
the CURRENT CONCEPT itself rather than an arbitrary example,
component, or subtopic.

Do NOT output the CORE CONCEPT SCOPE separately.

The final question, expected answer, and evaluation criteria
must all be based on the same CORE CONCEPT SCOPE.

============================================================
QUESTION RULES
============================================================

1. The CURRENT CONCEPT is the assessment target.

2. First determine the central meaning of the CURRENT CONCEPT
   from the RETRIEVED KNOWLEDGE.

3. Generate a question that tests that central meaning.

4. If the CURRENT CONCEPT describes a broad topic containing
   multiple components, functions, methods, or examples,
   assess the broader concept rather than selecting one
   arbitrary component.

5. Components and examples mentioned in the knowledge are
   supporting information unless the CURRENT CONCEPT itself
   represents that component.

6. If the CURRENT CONCEPT contains multiple components,
   functions, methods, stages, properties, or subtopics,
   do not automatically focus on only one of them.

7. When the CURRENT CONCEPT is broad, formulate the question
   at the same level of abstraction as the concept and assess
   its central role, purpose, behavior, or relationships as
   supported by the RETRIEVED KNOWLEDGE.

8. Do NOT generate a question whose answer could be fully
   correct while ignoring a major part of the CURRENT CONCEPT.

9. Prefer conceptual questions using:
   - what
   - why
   - how
   - purpose
   - role
   - explain
   - describe

10. Do NOT ask for simple example recall.

11. Do NOT ask about a minor example unless that example is
    itself the CURRENT CONCEPT.

12. The question must be answerable using ONLY the
    RETRIEVED KNOWLEDGE.

13. Do NOT use pretrained knowledge.

14. Do NOT introduce facts absent from the RETRIEVED KNOWLEDGE.

15. Keep the question appropriate for the student's level.





============================================================
QUESTION COVERAGE CHECK
============================================================

After generating the question, silently ask:

"Could a student answer this question correctly while
demonstrating understanding of only a small part of the
CURRENT CONCEPT?"

If YES, rewrite the question so that it assesses the central
meaning of the CURRENT CONCEPT.

If the CURRENT CONCEPT contains multiple major parts, make
sure the question covers the relevant parts needed to
demonstrate understanding of the concept.

Do NOT mention this check in the output.
CRITERIA CONSISTENCY CHECK:
Before returning the JSON, verify:
1. The expected answer directly answers the question.
2. Every evaluation criterion is supported by the expected answer.
3. A semantically equivalent paraphrase of the expected answer would satisfy the criteria.
4. No criterion requires information that is absent from the expected answer.

============================================================
EXPECTED ANSWER RULES
============================================================

Generate a concise answer that directly answers the question.

The answer must:

- use ONLY retrieved knowledge
- contain the important information needed to answer
  the question
- normally be 1-3 sentences
- avoid unnecessary details
- avoid unsupported examples
- avoid repeating the question


============================================================
CONCEPT SCOPE VALIDATION
============================================================

Before returning the answer, silently verify:

1. The question is about the CURRENT CONCEPT itself.

2. The question is not merely about an example mentioned
   inside the retrieved knowledge.

3. The question does not replace a multi-part concept with
   only one of its components.

4. If the CURRENT CONCEPT contains multiple major parts,
   the question must address the concept at the appropriate
   level of abstraction.

5. A student should need to understand the CURRENT CONCEPT,
   rather than only memorize one example or component, to
   answer correctly.

If any condition fails, rewrite the question.

Do NOT mention this validation in the output.

EVALUATION CRITERIA RULES:
- Generate 1 to 4 criteria.
- Every criterion must directly evaluate the answer to the generated question.
- Criteria must be derived from the expected answer and the question.
- Do NOT introduce additional facts from the retrieved knowledge merely because they are available.
- A student who gives the expected answer in their own words should be able to satisfy the criteria.
- Criteria should represent distinct pieces of understanding required by the question.
- Do not create duplicate criteria that express the same idea using different wording.
- Do not make a criterion stricter than the expected answer.
- Do not require examples, terminology, components, or distinctions that the question does not ask for.

- Never use vague criteria such as "addresses the central meaning",
  "shows understanding", or "is supported by the knowledge".
- Each criterion must describe a specific piece of knowledge that
  can be verified from the student's answer.
- Do not use internal prompt terms such as "CURRENT CONCEPT",
  "CORE CONCEPT SCOPE", or "RETRIEVED KNOWLEDGE" in the criteria.
============================================================
SELF-CONSISTENCY CHECK
============================================================

Before returning the JSON, verify:

1. The question tests the CURRENT CONCEPT.
2. The expected answer directly answers the question.
3. Every evaluation criterion is needed to answer the question.
4. No criterion requires information not asked by the question.
5. The misconception guidance refers specifically to this question.
6. Everything is supported by RETRIEVED KNOWLEDGE.

If a criterion is not directly relevant to the question,
remove it.

OUTPUT FORMAT:

Return EXACTLY ONE valid JSON object.

Do not write:
- CORE CONCEPT SCOPE
- QUESTION:
- EXPECTED ANSWER:
- EVALUATION CRITERIA:
- MISCONCEPTION GUIDANCE:
- explanations before the JSON
- explanations after the JSON
- markdown
- code fences

Return ONLY this JSON structure:

{{
  "question": "string",
  "expected_answer": "string",
  "evaluation_criteria": [
    "string"
  ],
  "misconception_guidance": "string"
}}

The response must begin with {{ and end with }}.

Before responding, verify:
1. The JSON is syntactically valid.
2. The question is about the CURRENT CONCEPT.
3. The expected answer directly answers the question.
4. Every evaluation criterion is supported by the expected answer.
5. A student who gives the expected answer in different words can satisfy the criteria.
6. No criterion introduces additional requirements absent from the expected answer.
7. The misconception guidance describes a genuine incorrect belief, not merely missing information.
"""

    response = generate_response(prompt).strip()

    data = _extract_json_object(response)

    question = str(
        data.get("question", "")
    ).strip()

    expected_answer = str(
        data.get("expected_answer", "")
    ).strip()

    evaluation_criteria = data.get(
        "evaluation_criteria",
        [],
    )

    misconception_guidance = str(
        data.get(
            "misconception_guidance",
            "",
        )
    ).strip()

    if not question:
        raise ValueError(
            f"Diagnostic question was empty for concept "
            f"'{concept.name}'."
        )

    if not expected_answer:
        raise ValueError(
            f"Diagnostic expected answer was empty for concept "
            f"'{concept.name}'."
        )

    if not isinstance(
        evaluation_criteria,
        list,
    ):
        evaluation_criteria = []

    evaluation_criteria = [
        str(item).strip()
        for item in evaluation_criteria
        if str(item).strip()
    ]

    if not evaluation_criteria:
        raise ValueError(
            f"No evaluation criteria generated for concept "
            f"'{concept.name}'."
        )

    return {
        "question": question,
        "expected_answer": expected_answer,
        "evaluation_criteria": evaluation_criteria,
        "misconception_guidance": misconception_guidance,
    }


def generate_diagnostic_question(
    db: Session,
    concept: Concept,
    student_level: str,
) -> dict:
    """
    Generate one diagnostic question for a concept using
    RAG knowledge.
    """

    knowledge_text = retrieve_diagnostic_knowledge(
        db=db,
        concept=concept,
    )

    content = generate_diagnostic_content(
        concept=concept,
        student_level=student_level,
        knowledge_text=knowledge_text,
    )

    return {
        "concept_id": concept.id,
        "concept": concept.name,
        "question": content["question"],
        "expected_answer": content["expected_answer"],
        "evaluation_criteria": content["evaluation_criteria"],
        "misconception_guidance": content[
            "misconception_guidance"
        ],
    }


def generate_diagnostic(
    db: Session,
    student_id: int,
    subject_id: int,
    student_level: str,
    limit: int = 5,
) -> list[dict]:
    """
    Generate a diagnostic assessment for a student.

    The diagnostic is topic-independent:

    - concepts come from the selected subject
    - knowledge comes from RAG
    - questions are generated by the LLM
    - evaluation criteria are generated with the question
    """

    if limit < 1:
        raise ValueError(
            "Diagnostic limit must be at least 1."
        )

    limit = min(limit, 20)

    concepts = select_diagnostic_concepts(
        db=db,
        student_id=student_id,
        subject_id=subject_id,
        limit=limit,
    )

    if not concepts:
        return []

    questions = []

    for concept in concepts:
        question = generate_diagnostic_question(
            db=db,
            concept=concept,
            student_level=student_level,
        )

        questions.append(question)

    return questions