import json

from app.schemas.curriculum_generation import GeneratedCurriculum
from app.tutor.tutor_service import generate_response


def generate_curriculum(topic: str) -> dict:
    prompt = f"""
You are an expert curriculum designer.

Create a structured learning curriculum for:

TOPIC:
{topic}

The curriculum must be suitable for a student learning this topic
from beginner level.

Requirements:

1. Create 5 to 12 important concepts.

2. Order the concepts logically from foundational to advanced.

3. Each concept must have:
   - a clear name
   - a concise description
   - a list of prerequisite concept names

4. Prerequisites must refer ONLY to concepts included in this
   curriculum.

5. A concept may have zero prerequisites.

6. Avoid duplicate concepts.

7. Do not create circular prerequisite relationships.

8. Focus on the core knowledge needed to understand the topic.

9. Do not include unrelated concepts.

10. Prerequisites must represent genuine conceptual dependencies.

11. Do not make concepts depend on another concept merely because
    they belong to the same subject.

12. Concepts at the same conceptual level should generally be allowed
    to have no relationship with each other.

13. Avoid unnecessary chains where one concept depends on another
    simply because it appeared earlier.

14. Do not create prerequisite relationships between alternative
    approaches or sibling concepts.

15. Only create a prerequisite relationship when understanding the
    prerequisite is genuinely useful or necessary for understanding
    the dependent concept.

16. Keep the curriculum suitable for a beginner.

17. Do not assume that concepts appearing earlier in the list are
    automatically prerequisites.

Return ONLY valid JSON in exactly this format:

{{
  "subject": "{topic}",
  "description": "Short description of the topic.",
  "concepts": [
    {{
      "name": "Concept 1",
      "description": "Description of concept 1.",
      "prerequisites": []
    }},
    {{
      "name": "Concept 2",
      "description": "Description of concept 2.",
      "prerequisites": ["Concept 1"]
    }}
  ]
}}

Generate the curriculum now.
"""

    response = generate_response(prompt).strip()

    # ---------------------------------------------------------
    # Remove accidental markdown code fences
    # ---------------------------------------------------------

    if response.startswith("```"):
        response = response.replace("```json", "")
        response = response.replace("```", "")
        response = response.strip()

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    try:
        curriculum = json.loads(response)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"LLM returned invalid curriculum JSON: {response}"
        ) from error

    # ---------------------------------------------------------
    # Validate generated curriculum
    # ---------------------------------------------------------

    try:
        validated_curriculum = GeneratedCurriculum.model_validate(
            curriculum
        )

    except Exception as error:
        raise ValueError(
            f"LLM returned an invalid curriculum structure: {curriculum}"
        ) from error

    # ---------------------------------------------------------
    # Return validated curriculum
    # ---------------------------------------------------------

    return validated_curriculum.model_dump()