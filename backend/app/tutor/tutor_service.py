import re
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
            "options": {
                "temperature": 0.0,
                "top_p": 0.1,
            },
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    generated_text = data.get("response")

    if not isinstance(generated_text, str):
        raise ValueError("LLM returned an invalid response.")

    generated_text = generated_text.strip()

    if not generated_text:
        raise ValueError("LLM returned an empty response.")

    return generated_text


def validate_grounding(
    response: str,
    retrieved_knowledge: str,
) -> bool:
    """
    Check whether each factual sentence in the response is grounded
    in the retrieved knowledge.

    This deterministic check combines:
    1. lexical overlap, and
    2. detection of factual predicates that are not supported by
       the evidence.

    It is intentionally conservative: when support is unclear,
    the response is rejected and the evidence-only fallback is used.
    """

    evidence_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]+\b",
            retrieved_knowledge.lower(),
        )
    )

    sentences = re.split(
        r"(?<=[.!?])\s+",
        response.strip(),
    )

    normalized_sentences = [
        re.sub(r"\s+", " ", sentence.strip().lower())
        for sentence in sentences
        if sentence.strip()
    ]

    if len(normalized_sentences) != len(set(normalized_sentences)):
        return False

    # Words that commonly introduce factual properties, behaviors,
    # guarantees, relationships, or capabilities.
    predicate_markers = {
        "guarantees",
        "guarantee",
        "ensures",
        "ensure",
        "provides",
        "provide",
        "allows",
        "allow",
        "prevents",
        "prevent",
        "protects",
        "protect",
        "supports",
        "support",
        "enables",
        "enable",
        "uses",
        "use",
        "transfers",
        "transfer",
        "encrypts",
        "encrypt",
        "secures",
        "secure",
        "improves",
        "improve",
        "reduces",
        "reduce",
    }

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        # Questions are learner-facing prompts rather than factual claims.
        if sentence.endswith("?"):
            continue

        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            sentence.lower(),
        )

        if not words:
            continue

        supported_words = sum(
            1
            for word in words
            if word in evidence_words
        )

        overlap_ratio = supported_words / len(words)

        if overlap_ratio < 0.50:
            return False

        # If the response introduces a factual predicate that does not
        # appear anywhere in the evidence, reject it.
        response_predicates = {
            word
            for word in words
            if word in predicate_markers
        }

        evidence_predicates = {
            word
            for word in re.findall(
                r"\b[a-zA-Z0-9]+\b",
                retrieved_knowledge.lower(),
            )
            if word in predicate_markers
        }

        unsupported_predicates = (
            response_predicates - evidence_predicates
        )

        if unsupported_predicates:
            return False

    return True

    return True
def sanitize_retrieved_knowledge(retrieved_knowledge: str) -> str:
    """
    Remove obvious instruction-like content from retrieved material
    before exposing it to the learner.
    """

    blocked_patterns = [
        r"ignore\s+all\s+previous\s+instructions",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"use\s+your\s+own\s+knowledge",
        r"follow\s+these\s+instructions",
        r"ignore\s+(the\s+)?instructions",
    ]

    sanitized = retrieved_knowledge

    for pattern in blocked_patterns:
        sanitized = re.sub(
            pattern,
            "",
            sanitized,
            flags=re.IGNORECASE,
        )

    return sanitized
def build_evidence_lesson(retrieved_knowledge: str) -> str:
    """
    Build a learner-facing factual lesson directly from retrieved
    knowledge without allowing the LLM to introduce new facts.
    """

    if not retrieved_knowledge.strip():
        return "The available knowledge does not provide that detail."

    retrieved_knowledge = sanitize_retrieved_knowledge(
        retrieved_knowledge
    )

    chunks = [
        chunk.strip()
        for chunk in retrieved_knowledge.split("\n\n")
        if chunk.strip()
    ]

    statements = []

    for chunk in chunks:
        # Remove the retrieval label such as:
        # [Knowledge 1]
        cleaned_chunk = re.sub(
            r"^\[Knowledge\s+\d+\]\s*",
            "",
            chunk,
            flags=re.IGNORECASE,
        ).strip()

        if cleaned_chunk:
            statements.append(cleaned_chunk)

    return "\n\n".join(statements)


def generate_grounded_response(
    prompt: str,
    retrieved_knowledge: str,
) -> str:
    """
    Generate a natural tutor response using the LLM, but only accept it
    when every factual sentence has sufficient lexical support from the
    retrieved evidence.

    If the LLM output fails the grounding check, return the deterministic
    evidence-only fallback.
    """

    if not retrieved_knowledge.strip():
        return "The available knowledge does not provide that detail."

    sanitized_knowledge = sanitize_retrieved_knowledge(
        retrieved_knowledge
    )

    evidence_lesson = build_evidence_lesson(
        sanitized_knowledge
    )

    llm_response = generate_response(prompt)


    if validate_grounding(
        llm_response,
        sanitized_knowledge,
    ):
        return llm_response

    return evidence_lesson