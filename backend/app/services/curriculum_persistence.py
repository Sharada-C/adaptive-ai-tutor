from sqlalchemy.orm import Session

from app.models.curriculum import Concept, Subject
from app.schemas.curriculum_generation import GeneratedCurriculum


def find_prerequisite_cycle(
    graph: dict[str, list[str]],
) -> list[str] | None:
    """Return one cycle as [a, b, ..., a] if the graph has one, else None.

    ``graph`` maps a concept to the concepts it requires. Iterative
    depth-first search with white/grey/black colouring.
    """

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {node: WHITE for node in graph}

    for start in graph:
        if colour[start] != WHITE:
            continue

        path = [start]
        iters = [iter(graph[start])]
        colour[start] = GREY

        while iters:
            for nxt in iters[-1]:
                if nxt not in colour:
                    continue

                if colour[nxt] == GREY:
                    return path[path.index(nxt):] + [nxt]

                if colour[nxt] == WHITE:
                    colour[nxt] = GREY
                    path.append(nxt)
                    iters.append(iter(graph[nxt]))
                    break
            else:
                colour[path.pop()] = BLACK
                iters.pop()

    return None


def save_generated_curriculum(
    db: Session,
    curriculum: GeneratedCurriculum,
    owner_id: int | None = None,
) -> Subject:
    """Validate and store a generated curriculum.

    ``owner_id`` makes the course private to that user; names only have to
    be unique among the same owner's courses (or among shared courses).
    """

    # ---------------------------------------------------------
    # 1. Check whether subject already exists
    # ---------------------------------------------------------

    existing_subject = (
        db.query(Subject)
        .filter(
            Subject.name == curriculum.subject.strip(),
            Subject.owner_id == owner_id
            if owner_id is not None
            else Subject.owner_id.is_(None),
        )
        .first()
    )

    if existing_subject:
        raise ValueError(
            f"Subject '{curriculum.subject}' already exists."
        )

    # ---------------------------------------------------------
    # 2. Validate concept names
    # ---------------------------------------------------------

    concept_names = [
        concept.name.strip()
        for concept in curriculum.concepts
    ]

    normalized_names = [
        name.lower()
        for name in concept_names
    ]

    if len(normalized_names) != len(set(normalized_names)):
        raise ValueError(
            "Generated curriculum contains duplicate concepts."
        )

    concept_name_set = set(normalized_names)

    # ---------------------------------------------------------
    # 3. Validate prerequisites
    # ---------------------------------------------------------

    for concept in curriculum.concepts:

        current_name = concept.name.strip()

        for prerequisite in concept.prerequisites:

            prerequisite_name = prerequisite.strip()

            if prerequisite_name.lower() == current_name.lower():
                raise ValueError(
                    f"Concept '{current_name}' cannot be its own "
                    "prerequisite."
                )

            if prerequisite_name.lower() not in concept_name_set:
                raise ValueError(
                    f"Prerequisite '{prerequisite_name}' for "
                    f"concept '{current_name}' does not exist."
                )

    graph = {
        concept.name.strip().lower(): [
            p.strip().lower() for p in concept.prerequisites
        ]
        for concept in curriculum.concepts
    }
    cycle = find_prerequisite_cycle(graph)

    if cycle:
        raise ValueError(
            "Circular prerequisites are not allowed: "
            + " -> ".join(cycle)
        )

    # ---------------------------------------------------------
    # 4. Create Subject
    # ---------------------------------------------------------

    subject = Subject(
        name=curriculum.subject.strip(),
        description=curriculum.description.strip(),
        owner_id=owner_id,
    )

    db.add(subject)

    # Flush so subject.id becomes available
    db.flush()

    # ---------------------------------------------------------
    # 5. Create Concepts
    # ---------------------------------------------------------

    concept_map: dict[str, Concept] = {}

    for generated_concept in curriculum.concepts:

        concept = Concept(
            subject_id=subject.id,
            name=generated_concept.name.strip(),
            description=generated_concept.description.strip(),
        )

        db.add(concept)

        concept_map[
            generated_concept.name.strip().lower()
        ] = concept

    # Flush so all concept IDs are available
    db.flush()

    # ---------------------------------------------------------
    # 6. Create prerequisite relationships
    # ---------------------------------------------------------

    for generated_concept in curriculum.concepts:

        concept = concept_map[
            generated_concept.name.strip().lower()
        ]

        for prerequisite_name in generated_concept.prerequisites:

            prerequisite = concept_map[
                prerequisite_name.strip().lower()
            ]

            concept.prerequisites.append(
                prerequisite
            )

    # ---------------------------------------------------------
    # 7. Commit transaction
    # ---------------------------------------------------------

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    # ---------------------------------------------------------
    # 8. Refresh subject
    # ---------------------------------------------------------

    db.refresh(subject)

    return subject