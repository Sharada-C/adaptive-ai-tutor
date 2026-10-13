import pytest

from app.tutor.quiz_service import generate_quiz


def test_quiz_generation_uses_only_retrieved_knowledge(monkeypatch):
    def fake_generate_response(prompt):
        return """
        {
            "question": "What is the purpose of page tables and the TLB?",
            "expected_answer": "Page tables map virtual addresses to physical addresses, and the TLB caches translations.",
            "difficulty": "hard"
        }
        """

    monkeypatch.setattr(
        "app.tutor.quiz_service.generate_response",
        fake_generate_response,
    )

    knowledge = (
        "Virtual memory allows processes to use an address space "
        "larger than available physical memory by using secondary storage."
    )

    with pytest.raises(
        ValueError,
        match="not sufficiently grounded in retrieved knowledge",
    ):
        generate_quiz(
            concept="Virtual Memory",
            concept_description="Virtual memory",
            student_level="intermediate",
            mastery_score=0.9,
            knowledge_text=knowledge,
        )
def test_quiz_generation_rejects_unsupported_claim(monkeypatch):
    def fake_generate_response(prompt):
        return """
        {
            "question": "Does virtual memory require every process to run entirely in RAM?",
            "expected_answer": "Yes, every process must fit entirely in physical RAM.",
            "difficulty": "hard"
        }
        """

    monkeypatch.setattr(
        "app.tutor.quiz_service.generate_response",
        fake_generate_response,
    )

    knowledge = (
        "Virtual memory allows processes to use an address space "
        "larger than available physical memory by using secondary storage."
    )

    with pytest.raises(ValueError):
        generate_quiz(
            concept="Virtual Memory",
            concept_description="Virtual memory",
            student_level="intermediate",
            mastery_score=0.9,
            knowledge_text=knowledge,
        )