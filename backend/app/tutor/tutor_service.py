import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.2:3b"


def generate_response(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    return data["response"].strip()


def generate_grounded_response(
    prompt: str,
    retrieved_knowledge: str,
) -> str:
    """
    Generate a response that is explicitly constrained
    to the supplied retrieved knowledge.

    The model is instructed not to use outside knowledge.
    """

    grounded_prompt = f"""
You are a strictly evidence-grounded AI tutor.

Your response MUST be based ONLY on the EVIDENCE provided below.

====================
EVIDENCE
====================

{retrieved_knowledge}

====================
TASK
====================

{prompt}

====================
STRICT RULES
====================

1. The EVIDENCE is the only factual source you may use.

2. Do NOT use information from your pretrained knowledge.

3. Do NOT infer additional technical facts from a term merely
   because you recognize the term.

4. If the evidence says that something is an example, you may
   say that it is an example.

5. If the evidence does NOT explain what an example does,
   do NOT explain what it does.

6. Do NOT expand abbreviations unless the expansion appears
   explicitly in the evidence.

7. Do NOT invent real-world examples involving technical
   behavior that is not present in the evidence.

8. Analogies are allowed only when they explain information
   already present in the evidence and do not introduce new
   technical claims.

9. If a requested detail is not present in the evidence, say:
   "The available knowledge does not provide that detail."

10. Every factual statement in the final answer must be
    directly supported by the evidence.

11. Stay focused on the requested concept.

12. End with ONE short understanding-check question.

Before returning the answer, silently check every factual
statement against the EVIDENCE. Remove any statement that
cannot be directly supported.

Return only the teaching explanation and the final question.
"""

    return generate_response(grounded_prompt)