from app.db.database import SessionLocal
from app.models import Concept, ConceptMastery
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
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.username == "pytest_planner_user")
            .first()
        )

        if user is None:
            user = User(username="pytest_planner_user")
            db.add(user)
            db.flush()

        student = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == user.id)
            .first()
        )

        if student is None:
            student = StudentProfile(
                user_id=user.id,
                learning_level="beginner",
            )
            db.add(student)
            db.flush()

        planner_student_id = student.id

        process_management = (
            db.query(Concept)
            .filter(
                Concept.subject_id == 1,
                Concept.name == "Process Management",
            )
            .first()
        )

        process_scheduling = (
            db.query(Concept)
            .filter(
                Concept.subject_id == 1,
                Concept.name == "Process Scheduling",
            )
            .first()
        )

        assert process_management is not None
        assert process_scheduling is not None

        # Keep the prerequisite below the mastery threshold.
        mastery = (
            db.query(ConceptMastery)
            .filter(
                ConceptMastery.student_id == planner_student_id,
                ConceptMastery.concept_id == process_management.id,
            )
            .first()
        )

        if mastery is None:
            mastery = ConceptMastery(
                student_id=planner_student_id,
                concept_id=process_management.id,
                mastery_score=0.50,
                attempts=1,
                correct_answers=0,
            )
            db.add(mastery)
        else:
            mastery.mastery_score = 0.50

        # Make Process Scheduling unmastered too.
        scheduling_mastery = (
            db.query(ConceptMastery)
            .filter(
                ConceptMastery.student_id == planner_student_id,
                ConceptMastery.concept_id == process_scheduling.id,
            )
            .first()
        )

        if scheduling_mastery is None:
            db.add(
                ConceptMastery(
                    student_id=planner_student_id,
                    concept_id=process_scheduling.id,
                    mastery_score=0.0,
                    attempts=0,
                    correct_answers=0,
                )
            )
        else:
            scheduling_mastery.mastery_score = 0.0

        db.commit()

        next_concept = select_next_concept(
            db=db,
            student_id=planner_student_id,
            subject_id=1,
        )

        assert next_concept is not None
        assert next_concept.id == process_management.id
        assert next_concept.id != process_scheduling.id

    finally:
        db.close()
