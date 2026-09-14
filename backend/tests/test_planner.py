from app.db.database import SessionLocal
from app.models import Concept, ConceptMastery
from app.services.learning_planner import select_next_concept


def test_select_next_concept_returns_none_when_subject_is_mastered(
    test_student,
):
    db = SessionLocal()

    try:
        concepts = (
            db.query(Concept)
            .filter(Concept.subject_id == 1)
            .all()
        )

        for concept in concepts:
            mastery = (
                db.query(ConceptMastery)
                .filter(
                    ConceptMastery.student_id == test_student,
                    ConceptMastery.concept_id == concept.id,
                )
                .first()
            )

            if mastery:
                mastery.mastery_score = 1.0
            else:
                db.add(
                    ConceptMastery(
                        student_id=test_student,
                        concept_id=concept.id,
                        mastery_score=1.0,
                        attempts=1,
                        correct_answers=1,
                    )
                )

        db.commit()

        next_concept = select_next_concept(
            db=db,
            student_id=test_student,
            subject_id=1,
        )

        assert next_concept is None

    finally:
        db.close()