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
        misconception_text = "None identified."

    retrieval_query = (
        f"{context['concept']}. "
        f"Student misconception: {misconception_text}"
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
    print("\n===== RETRIEVED KNOWLEDGE FOR RETEACH =====")
    print(knowledge_text)
    print("===========================================\n")

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

12. Do not use pretrained knowledge to fill missing information.

13. Do not expand abbreviations unless the expansion appears in
    the RETRIEVED KNOWLEDGE.

14. A term being mentioned in the RETRIEVED KNOWLEDGE does NOT
    mean that its properties, purpose, function, behavior, or use
    are known.

    Only reproduce a fact about a term if that exact fact is
    explicitly stated in the RETRIEVED KNOWLEDGE.

    For example, if the knowledge says:
    "TCP is an example of a network protocol."

    you may state:
    "TCP is an example of a network protocol."

    You may NOT state:
    "TCP transfers data over the internet."

    unless the retrieved knowledge explicitly states that.

14. Keep the lesson appropriate for the student's level.

18. Do NOT output labels such as:
    "Concept Description:"
    "Retrieved Knowledge:"
    "Teaching Rules:"
    "Lesson:"
    "Final Question:"
    or "Output:".

19. Do NOT describe your instructions, reasoning, retrieved
    knowledge, prompt, or teaching rules.

20. Do NOT reproduce the RETRIEVED KNOWLEDGE verbatim unless
    necessary. Present it as a natural explanation for the student.15. End with exactly ONE short understanding-check question.

16. The answer to the question MUST appear explicitly in the
    RETRIEVED KNOWLEDGE.

17. Before creating the question, identify a specific sentence or
    statement in the RETRIEVED KNOWLEDGE that directly contains
    its answer.

18. Ask only about information directly stated in that sentence
    or statement.

19. If the retrieved knowledge says that something is an example,
    you may ask the learner to identify that it is an example.

20. Do NOT ask what an example does, how it works, why it is used,
    its purpose, function, role, behavior, effect, benefit, or
    properties unless that information is explicitly stated.

21. Do NOT ask about TCP, UDP, HTTP, HTTPS, IP, or any other listed
    entity merely because its name appears in the retrieved
    knowledge. Its name appearing alone is NOT evidence about
    what it does.

22. For example, if the retrieved knowledge says:
    "HTTP, HTTPS, TCP, UDP, and IP are examples of network
    protocols."
    an allowed question is:
    "Which of the following is an example of a network protocol?"
    A question such as:
    "What is the primary function of TCP?"
    is NOT allowed unless the function of TCP is explicitly stated.

23. If no suitable directly supported fact exists for a question,
    ask a question about another fact that is explicitly stated.

OUTPUT RULES
------------

24. Return ONLY the learner-facing lesson.

25. Do NOT output or repeat any part of this prompt.

21. Do NOT include headings that describe the internal structure
    of the prompt.

22. The response should read as if a tutor is directly teaching
    the student.

23. The final question must appear naturally at the end of the
    lesson without a "Final Question:" label.

GROUNDING CHECK
---------------
Before returning the answer, check every factual statement.

If a factual statement cannot be directly supported by the
RETRIEVED KNOWLEDGE, remove it.

Do not explain your grounding process.

Return only the lesson and one final understanding-check question.
"""

    explanation = generate_grounded_response(
        prompt=prompt,
        retrieved_knowledge=knowledge_text,
    )

    

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
    has_specific_misconception = bool(misconceptions)

    if not misconceptions:
        misconceptions = [
            "No specific misconception was identified. The student's mastery is low, so provide a clear explanation of the core ideas."
        ]

    misconceptions = list(dict.fromkeys(misconceptions))

    if has_specific_misconception:
        misconception_text = "\n".join(
            f"- {item}"
            for item in misconceptions
        )
    else:
        misconception_text = "None identified."

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
- Do not explain the function, behavior, relationship, or purpose of
  any entity unless that information is explicitly stated in the
  retrieved knowledge.
- If the retrieved knowledge does not explain a detail, explicitly
  say that the available knowledge does not provide that detail.
- Do not expand, interpret, or infer anything from a short statement
  in the retrieved knowledge.
- If the retrieved knowledge only lists an entity, you may only state
  that the entity is listed.
- Do not infer its function, purpose, behavior, relationship, or role.
- If the retrieved knowledge does not contain enough information,
  do not guess.
- Do not introduce unrelated concepts unless they are necessary
  to explain the current concept.


RETEACHING TASK
---------------
If a specific misconception was identified, reteach the concept
specifically to correct that misconception.

If no specific misconception was identified, reteach the concept
by clearly explaining its core ideas. Do not claim that the
student misunderstood a specific fact.

- Every example must be consistent with the retrieved knowledge.
- Do not introduce domain-specific behavior, relationships, or
  properties that are absent from the retrieved knowledge.
- Any example used during reteaching must be directly supported by
  the retrieved knowledge.
- Do not make claims that contradict the retrieved knowledge.

Rules:
- If a specific misconception was identified, explain what the student misunderstood and contrast it with the correct idea.
- If no specific misconception was identified, explain the core concept directly without saying that the student misunderstood anything.
- Do not use examples or analogies unless they are explicitly supported by the retrieved knowledge.
- If the retrieved knowledge does not contain a suitable example,
  do not invent one.
- Do not use familiar real-world examples merely because they are
  commonly associated with the concept.
- Do not shame or criticize the student.
- Do not repeat the previous explanation verbatim.
- Keep the explanation appropriate for the student's level.
- If no specific misconception was identified, organize the retrieved
  knowledge into a clear explanation of the core concept rather than
  repeating the same statement in different words.
- Do NOT use analogies, fictional scenarios, stories, or
   invented examples.
- If a specific misconception was identified, focus on correcting it.
- If no specific misconception was identified, focus on clearly
  teaching the core concept.
- Use only facts and examples explicitly present in the EVIDENCE.
FINAL GROUNDING CHECK
---------------------
Before producing the answer, remove any sentence that is not directly
supported by the RETRIEVED KNOWLEDGE or CONCEPT DESCRIPTION.

Do NOT use analogies, comparisons, fictional scenarios, stories,
or phrases such as "Think of..." or "Imagine...".

Do NOT state why learning the concept is useful or important unless
that statement is explicitly supported by the retrieved knowledge.

Do NOT add information merely because it is generally true.
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