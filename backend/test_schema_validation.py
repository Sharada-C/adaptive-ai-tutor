from pydantic import ValidationError

from app.schemas.assessment import AssessmentCreate
from app.schemas.diagnostic import DiagnosticStartRequest, DiagnosticSubmitRequest
from app.schemas.evaluation import EvaluationRequest
from app.schemas.quiz import QuizRequest
from app.schemas.student import MasteryUpdate
from app.schemas.curriculum import SubjectCreate, ConceptCreate
from app.schemas.curriculum_generation import CurriculumGenerateRequest


tests = [
    ("Assessment negative score",
     lambda: AssessmentCreate(
         concept_id=1,
         question="Q",
         student_answer="A",
         score=-0.1,
         result="correct",
     )),

    ("Assessment score above 1",
     lambda: AssessmentCreate(
         concept_id=1,
         question="Q",
         student_answer="A",
         score=1.1,
         result="correct",
     )),

    ("Assessment invalid concept ID",
     lambda: AssessmentCreate(
         concept_id=0,
         question="Q",
         student_answer="A",
         score=1.0,
         result="correct",
     )),

    ("Diagnostic invalid student ID",
     lambda: DiagnosticStartRequest(
         student_id=0,
         subject_id=1,
     )),

    ("Diagnostic invalid limit",
     lambda: DiagnosticStartRequest(
         student_id=1,
         subject_id=1,
         limit=21,
     )),

    ("Evaluation invalid concept ID",
     lambda: EvaluationRequest(
         student_id=1,
         concept_id=0,
         question="Q",
         expected_answer="A",
         student_answer="A",
     )),

    ("Quiz invalid student ID",
     lambda: QuizRequest(
         student_id=0,
         concept_id=1,
     )),

    ("Mastery invalid score",
     lambda: MasteryUpdate(
         concept_id=1,
         mastery_score=1.5,
     )),

    ("Mastery negative attempts",
     lambda: MasteryUpdate(
         concept_id=1,
         mastery_score=0.5,
         attempts=-1,
     )),

    ("Subject empty name",
     lambda: SubjectCreate(name="")),

    ("Concept empty name",
     lambda: ConceptCreate(name="")),

    ("Curriculum topic too long",
     lambda: CurriculumGenerateRequest(topic="x" * 101)),
]


passed = 0

for name, test in tests:
    try:
        test()
        print(f"FAIL | {name} | Invalid input was accepted")
    except ValidationError:
        print(f"PASS | {name} | Invalid input rejected")
        passed += 1

print()
print(f"Passed: {passed}/{len(tests)}")

if passed != len(tests):
    raise SystemExit(1)
