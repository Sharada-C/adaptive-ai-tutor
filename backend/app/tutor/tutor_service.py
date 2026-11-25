import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.ollama_client import post_json


OLLAMA_URL = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
MODEL_NAME = settings.llm_model


def generate_response(prompt: str, model: str | None = None) -> str:
    data = post_json(
        OLLAMA_URL,
        {
            "model": model or MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "top_p": 0.1,
            },
        },
    )

    generated_text = data.get("response")

    if not isinstance(generated_text, str):
        raise ValueError("LLM returned an invalid response.")

    generated_text = generated_text.strip()

    if not generated_text:
        raise ValueError("LLM returned an empty response.")

    return generated_text


def _predicate_base(word: str, markers: set[str]) -> str:
    """'uses' and 'use' are the same predicate."""

    if word.endswith("s") and word[:-1] in markers:
        return word[:-1]

    return word


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
            _predicate_base(word, predicate_markers)
            for word in words
            if word in predicate_markers
        }

        evidence_predicates = {
            _predicate_base(word, predicate_markers)
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
MAX_EVIDENCE_SENTENCES = 6
MAX_EVIDENCE_WORDS = 170
MAX_SENTENCE_WORDS = 45

_FOCUS_STOPWORDS = frozenset(
    "a an the of to in on for and or but is are was were be been it its this "
    "that these those as at by with from into than then which who what when "
    "where how why not no can may will has have had their there they them".split()
)


def _focus_stems(text: str) -> set[str]:
    return {
        word[:5]
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in _FOCUS_STOPWORDS and len(word) > 2
    }


def _select_relevant(sentences: list[str], focus: str) -> list[str]:
    """Keep the few sentences most related to ``focus``, in original order.

    Study material can be whole articles; showing every retrieved chunk
    buries the point. With no focus the first sentences are kept.
    """

    if len(sentences) <= MAX_EVIDENCE_SENTENCES and (
        sum(len(sentence.split()) for sentence in sentences) <= MAX_EVIDENCE_WORDS
    ):
        return sentences

    focus_stems = _focus_stems(focus)

    # Sentences that share nothing with the concept are noise, not evidence.
    if focus_stems:
        # The concept name comes first in ``focus``; a sentence must mention
        # it, or share at least two words with the whole focus.
        name_stems = _focus_stems(focus.split(". ")[0])

        related = [
            s
            for s in sentences
            if (_focus_stems(s) & name_stems)
            or len(_focus_stems(s) & focus_stems) >= 2
        ]

        if not related:
            return []

        sentences = related

    # Very long sentences are usually list dumps; prefer concise ones
    # unless there is nothing else.
    concise = [
        i
        for i, sentence in enumerate(sentences)
        if len(sentence.split()) <= MAX_SENTENCE_WORDS
    ]
    candidates = concise if len(concise) >= 3 else list(range(len(sentences)))

    scored = sorted(
        candidates,
        key=lambda i: (
            -len(_focus_stems(sentences[i]) & focus_stems),
            i,
        ),
    )

    chosen: list[int] = []
    words = 0

    for index in scored:
        length = len(sentences[index].split())

        if chosen and words + length > MAX_EVIDENCE_WORDS:
            continue

        chosen.append(index)
        words += length

        if len(chosen) >= MAX_EVIDENCE_SENTENCES:
            break

    return [sentences[i] for i in sorted(chosen)]


def build_evidence_lesson(
    retrieved_knowledge: str,
    focus: str = "",
) -> str:
    """
    Build a learner-facing factual lesson directly from retrieved
    knowledge without allowing the LLM to introduce new facts.

    ``focus`` (concept name/description, question...) picks which
    sentences are shown when the evidence is long.
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

    all_sentences: list[str] = []
    seen_sentences = set()

    for chunk in chunks:
        cleaned_chunk = re.sub(
            r"^\[Knowledge\s+\d+\]\s*",
            "",
            chunk,
            flags=re.IGNORECASE,
        ).strip()

        if not cleaned_chunk:
            continue

        sentences = re.split(
            r"(?<=[.!?])\s+",
            cleaned_chunk,
        )

        # Chunks are cut at fixed word counts, so one can begin in the
        # middle of a sentence. That broken beginning is not shown.
        if len(sentences) > 1 and sentences[0][:1].islower():
            sentences = sentences[1:]

        for sentence in sentences:
            sentence = sentence.strip()

            sentence = re.sub(
                r"^Process Management\s+(?=Process management\s+is\b)",
                "",
                sentence,
                flags=re.IGNORECASE,
            )

            if not sentence:
                continue

            normalized = re.sub(
                r"\s+",
                " ",
                sentence.lower(),
            )

            if normalized in seen_sentences:
                continue

            seen_sentences.add(normalized)
            all_sentences.append(sentence)

    selected = _select_relevant(all_sentences, focus)

    if not selected:
        return (
            "The study material does not cover this concept in detail yet. "
            "Upload notes or a PDF for it to get a grounded explanation."
        )

    return " ".join(selected)


@dataclass
class GroundedResult:
    text: str
    # "llm": the model's wording passed the grounding check.
    # "extractive": deterministic text built directly from the study material.
    mode: str


def grounded_response(
    prompt: str,
    retrieved_knowledge: str,
    focus: str = "",
) -> GroundedResult:
    """
    Generate a tutor response with the LLM and accept it only when every
    factual sentence has sufficient support in the retrieved evidence;
    otherwise return the deterministic evidence-only lesson. The result
    says which of the two the student is looking at.
    """

    if not retrieved_knowledge.strip():
        return GroundedResult(
            "The available knowledge does not provide that detail.",
            "extractive",
        )

    sanitized_knowledge = sanitize_retrieved_knowledge(
        retrieved_knowledge
    )

    evidence_lesson = build_evidence_lesson(
        sanitized_knowledge,
        focus=focus,
    )

    llm_response = generate_response(prompt)

    if validate_grounding(
        llm_response,
        sanitized_knowledge,
    ):
        return GroundedResult(llm_response, "llm")

    return GroundedResult(evidence_lesson, "extractive")


def generate_grounded_response(
    prompt: str,
    retrieved_knowledge: str,
) -> str:
    """Text-only form of :func:`grounded_response`."""

    return grounded_response(prompt, retrieved_knowledge).text
