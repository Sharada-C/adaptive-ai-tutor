from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.tutor.context_builder import build_tutor_context
from app.tutor.tutor_service import generate_response, generate_grounded_response
from app.rag.retriever import retrieve_relevant_chunks_with_scores


router = APIRouter(
    prefix="/tutor",
    tags=["Tutor"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


class LessonRequest(BaseModel):
    student_id: int
    concept_id: int


class RetrievedKnowledge(BaseModel):
    content: str
    source: str
    similarity: float


class LessonResponse(BaseModel):
    concept: str
    explanation: str
    retrieved_knowledge: list[RetrievedKnowledge]


class ReteachRequest(BaseModel):
    student_id: int
    concept_id: int


class ReteachResponse(BaseModel):
    concept: str
    action: str
    misconceptions: list[str]
    explanation: str


def retrieve_knowledge(
    db: Session,
    query: str,
    concept_id: int,
    limit: int = 3,
):
    """
    Retrieve concept-specific knowledge using pgvector.

    Returns both the knowledge text used by the LLM
    and retrieval metadata for the API response.
    """

    results = retrieve_relevant_chunks_with_scores(
        db=db,
        query=query,
        concept_id=concept_id,
        limit=limit,
    )

    if not results:
        knowledge_text = "No retrieved knowledge available."
    else:
        knowledge_text = "\n\n".join(
            f"[Knowledge {index}]\n{item['chunk'].content}"
            for index, item in enumerate(
                results,
                start=1,
            )
        )

    return results, knowledge_text


@router.post(
    "/lesson",
    response_model=LessonResponse,
)
def generate_lesson(
    request: LessonRequest,
    db: Session = Depends(get_db),
):
    try:
        context = build_tutor_context(
            db=db,
            student_id=request.student_id,
            concept_id=request.concept_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    misconceptions = context["misconceptions"]

    if misconceptions:
        misconception_text = "\n".join(
            f"- {item}"
            for item in misconceptions
        )
    else:
        misconception_text = "None"

    # Retrieve relevant knowledge for the current concept.
    retrieval_query = (
        f"Concept: {context['concept']}. "
        f"Description: {context['concept_description']}"
        
    )

    if misconceptions:
        retrieval_query += (
            f" Known misconception: {misconception_text}"
        )

    knowledge_chunks, knowledge_text = retrieve_knowledge(
        db=db,
        query=retrieval_query,
        concept_id=request.concept_id,
        limit=2,
    )

    prompt = f"""
You are an evidence-grounded academic tutor.

Your task is to teach the CURRENT CONCEPT using ONLY the
RETRIEVED KNOWLEDGE.

STUDENT LEVEL
-------------
{context["student_level"]}

SUBJECT
-------
{context["subject"]}

CURRENT CONCEPT
---------------
{context["concept"]}

CONCEPT DESCRIPTION
-------------------
{context["concept_description"]}

KNOWN MISCONCEPTIONS
--------------------
{misconception_text}

RETRIEVED KNOWLEDGE
-------------------
{knowledge_text}

TEACHING RULES
--------------
1. Explain only information explicitly contained in the
   RETRIEVED KNOWLEDGE.

2. You may simplify the wording of the retrieved knowledge,
   but you must not add new factual information.

3. You may combine two statements from the retrieved knowledge
   when doing so does not create a new claim.

4. Do not explain a term merely because you recognize it.

5. If a term, example, component, method, or subtopic is only
   mentioned in the RETRIEVED KNOWLEDGE, do not add facts about
   it that are not explicitly provided.

6. Do not expand a listed example or component into a detailed
   explanation unless that explanation is supported by the
   RETRIEVED KNOWLEDGE.

7. Do not introduce technical, mathematical, scientific, or
   domain-specific details that are absent from the
   RETRIEVED KNOWLEDGE.

8. Do not create a scenario or example that requires facts
   not contained in the RETRIEVED KNOWLEDGE.

9. If an example is useful, use only information explicitly
   supported by the RETRIEVED KNOWLEDGE.

10. Do not infer additional properties, relationships, causes,
    effects, procedures, or behaviors merely because they are
    commonly associated with the CURRENT CONCEPT.

11. If information needed to explain a detail is missing, say:
    "The available knowledge does not provide that detail."

12. If information needed to explain something is missing, say:
    "The available knowledge does not provide that detail."

13. Do not use pretrained knowledge to fill missing information.

14. Do not expand abbreviations unless the expansion appears in
    the retrieved knowledge.

15. Keep the lesson appropriate for the student's level.

16. End with ONE short question whose answer can be found directly
    in the retrieved knowledge.

GROUNDING CHECK
---------------
Before returning the answer, check every factual statement.

If a factual statement cannot be directly supported by the
RETRIEVED KNOWLEDGE, remove it.

Do not explain your grounding process.

Return only the lesson and one final understanding-check question.
"""

    explanation = generate_response(prompt)

    return LessonResponse(
    concept=context["concept"],
    explanation=explanation,
    retrieved_knowledge=[
        RetrievedKnowledge(
            content=item["chunk"].content,
            source=item["source"],
            similarity=round(item["similarity"], 4),
        )
        for item in knowledge_chunks
    ],
)


@router.post(
    "/reteach",
    response_model=ReteachResponse,
)
def reteach(
    request: ReteachRequest,
    db: Session = Depends(get_db),
):
    try:
        context = build_tutor_context(
            db=db,
            student_id=request.student_id,
            concept_id=request.concept_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    misconceptions = context["misconceptions"]

    if not misconceptions:
        raise HTTPException(
            status_code=400,
            detail="No active misconception found for this concept.",
        )

    misconception_text = "\n".join(
        f"- {item}"
        for item in misconceptions
    )

    # Include the misconception in the retrieval query
    # so that the retrieved knowledge is relevant to the
    # specific misunderstanding.
    retrieval_query = (
        f"{context['concept']}. "
        f"Student misconception: {misconception_text}"
    )

    knowledge_chunks, knowledge_text = retrieve_knowledge(
        db=db,
        query=retrieval_query,
        concept_id=request.concept_id,
        limit=3,
    )

    prompt = f"""
You are an adaptive academic tutor.

STUDENT LEVEL
-------------
{context["student_level"]}

SUBJECT
-------
{context["subject"]}

CONCEPT
-------
{context["concept"]}

CONCEPT DESCRIPTION
-------------------
{context["concept_description"]}

CURRENT MASTERY
---------------
{context["mastery_score"]}

ACTIVE MISCONCEPTIONS
---------------------
{misconception_text}

RETRIEVED KNOWLEDGE
-------------------
{knowledge_text}

GROUNDING RULES
---------------
- Use the retrieved knowledge as the primary factual source.
- The concept description may provide additional context, but
  retrieved knowledge takes priority.
- Teach only the CURRENT CONCEPT within the SUBJECT context.
- Do not contradict the retrieved knowledge.
- Every factual claim must be supported by the retrieved knowledge
  or by the concept description.
- Do not invent detailed examples or protocol behavior that is not
  present in the retrieved knowledge.
- When giving an example, use only entities, relationships, and
  behaviors supported by the retrieved knowledge.
- If the retrieved knowledge does not explain a detail, explicitly
  say that the available knowledge does not provide that detail.
- Do not expand a short statement in the retrieved knowledge into
  unsupported technical claims.
- If the retrieved knowledge does not contain enough information,
  do not guess.
- Do not introduce unrelated concepts unless they are necessary
  to explain the current concept.

RETEACHING TASK
---------------
Your task is to reteach the concept specifically to correct
the student's misconception.
- Every example must be consistent with the retrieved knowledge.
- Do not introduce domain-specific behavior, relationships, or
  properties that are absent from the retrieved knowledge.
- Any example used during reteaching must be directly supported by
  the retrieved knowledge.
- Do not make claims that contradict the retrieved knowledge.

Rules:
- Clearly explain what the student misunderstood.
- Contrast the incorrect idea with the correct idea.
- Use a simple concrete example.
- Do not shame or criticize the student.
- Do not repeat the previous explanation verbatim.
- Keep the explanation appropriate for the student's level.
- Focus on correcting the active misconception.
- End with ONE short question that checks whether the misconception
  has been corrected.
- Before returning the explanation, internally check that the example
  does not contradict the retrieved knowledge or the misconception.

Return the teaching explanation and the checking question.
"""

    explanation = generate_grounded_response(
        prompt=prompt,
        retrieved_knowledge=knowledge_text,
    )

    return ReteachResponse(
        concept=context["concept"],
        action="reteach",
        misconceptions=misconceptions,
        explanation=explanation,
    )