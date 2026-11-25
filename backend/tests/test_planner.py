import uuid

from app.db.database import SessionLocal
from app.models import Concept, ConceptMastery, Subject
from app.models.student import User, StudentProfile
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


def test_select_next_concept_respects_prerequisites():
    """The planner must not pick a concept whose prerequisite is unmastered.

    The test builds its own subject so it does not depend on whatever
    courses exist in the developer's database, and removes it afterwards.
    """

    db = SessionLocal()

    subject = None
    user = None
    student = None
    concepts = []

    try:
        subject = Subject(
            name="Planner Prerequisite Test Subject",
            description="Created by test_planner.py.",
        )
        db.add(subject)
        db.flush()

        process_management = Concept(
            subject_id=subject.id,
            name="Process Management",
            description="Prerequisite concept.",
        )
        process_scheduling = Concept(
            subject_id=subject.id,
            name="Process Scheduling",
            description="Requires Process Management.",
        )
        concepts = [process_management, process_scheduling]
        db.add_all(concepts)
        db.flush()

        process_scheduling.prerequisites.append(process_management)

        user = User(username=f"pytest_planner_{uuid.uuid4().hex[:8]}")
        db.add(user)
        db.flush()

        student = StudentProfile(
            user_id=user.id,
            learning_level="beginner",
        )
        db.add(student)
        db.flush()

        # The prerequisite is below the mastery threshold, and the
        # dependent concept has not been started.
        db.add(
            ConceptMastery(
                student_id=student.id,
                concept_id=process_management.id,
                mastery_score=0.50,
                attempts=1,
                correct_answers=0,
            )
        )
        db.add(
            ConceptMastery(
                student_id=student.id,
                concept_id=process_scheduling.id,
                mastery_score=0.0,
                attempts=0,
                correct_answers=0,
            )
        )

        db.commit()

        next_concept = select_next_concept(
            db=db,
            student_id=student.id,
            subject_id=subject.id,
        )

        assert next_concept is not None
        assert next_concept.id == process_management.id
        assert next_concept.id != process_scheduling.id

    finally:
        db.rollback()

        if student is not None:
            db.query(ConceptMastery).filter(
                ConceptMastery.student_id == student.id
            ).delete()
            db.delete(student)

        if user is not None:
            db.delete(user)

        for concept in concepts:
            concept.prerequisites.clear()

        db.flush()

        for concept in concepts:
            db.delete(concept)

        if subject is not None:
            db.delete(subject)

        db.commit()
        db.close()
