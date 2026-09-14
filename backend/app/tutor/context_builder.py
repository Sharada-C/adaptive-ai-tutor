from sqlalchemy.orm import Session

from app.models.curriculum import Concept, Subject
from app.models.student import (
    ConceptMastery,
    Misconception,
    StudentProfile,
)


def build_tutor_context(
    db: Session,
    student_id: int,
    concept_id: int,
) -> dict:

    student = db.get(StudentProfile, student_id)

    if not student:
        raise ValueError("Student profile not found")

    concept = db.get(Concept, concept_id)

    if not concept:
        raise ValueError("Concept not found")

    subject = db.get(Subject, concept.subject_id)

    mastery = (
        db.query(ConceptMastery)
        .filter(
            ConceptMastery.student_id == student_id,
            ConceptMastery.concept_id == concept_id,
        )
        .first()
    )

    misconceptions = (
        db.query(Misconception)
        .filter(
            Misconception.student_id == student_id,
            Misconception.concept_id == concept_id,
            Misconception.resolved.is_(False),
        )
        .all()
    )

    return {
        "student_level": student.learning_level,
        "subject": subject.name if subject else "Unknown",
        "concept": concept.name,
        "concept_description": concept.description,
        "mastery_score": mastery.mastery_score if mastery else 0.0,
        "misconceptions": [
            misconception.description
            for misconception in misconceptions
        ],
    }