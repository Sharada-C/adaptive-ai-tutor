"""Evidence-only lessons must be short and about the concept, not a dump."""

from app.tutor import tutor_service
from app.tutor.tutor_service import build_evidence_lesson, grounded_response

CELL_WALL = (
    "Plant cells have cell walls composed of cellulose, hemicelluloses, and "
    "pectin. Cell walls provide shape to the tissues and organs of the plant. "
    "The cell wall is flexible during growth and has small pores called "
    "plasmodesmata. The cell wall protects the cell and prevents it from "
    "bursting when water enters."
)
XYLEM = (
    "Xylem is a complex vascular tissue composed of water-conducting "
    "tracheids. Tracheids are elongated cells with lignified thickening. "
    "Vessel elements are hollow cells without end walls. "
    "Phloem is a tissue that conducts sugars. Sieve tubes are aligned "
    "end to end. Companion cells support the sieve tubes. "
    "Sclerenchyma fibres give strength to leaves and stems."
)


def _evidence(*chunks):
    return "\n\n".join(
        f"[Knowledge {i}]\n{chunk}" for i, chunk in enumerate(chunks, 1)
    )


def test_long_evidence_is_cut_down_to_the_relevant_sentences():
    evidence = _evidence(XYLEM, CELL_WALL, XYLEM)

    lesson = build_evidence_lesson(evidence, focus="Cell Structure cell wall")

    assert "Cell walls provide shape" in lesson
    assert "bursting when water enters" in lesson
    assert "Companion cells" not in lesson
    assert "Sclerenchyma" not in lesson
    assert len(lesson.split()) <= 180


def test_a_chunk_that_starts_mid_sentence_loses_its_broken_beginning():
    chunk = "the wall thickening are possible. " + CELL_WALL

    lesson = build_evidence_lesson(
        _evidence(chunk, XYLEM), focus="cell wall"
    )

    assert "wall thickening are possible" not in lesson
    assert "Cell walls provide shape" in lesson


def test_short_evidence_is_still_returned_whole():
    evidence = _evidence("Cells are small. Cells have walls.")

    assert build_evidence_lesson(evidence, focus="cells") == (
        "Cells are small. Cells have walls."
    )


def test_selected_sentences_keep_their_original_order():
    evidence = _evidence(CELL_WALL, XYLEM)

    lesson = build_evidence_lesson(evidence, focus="bursting water cellulose")

    assert lesson.index("cellulose") < lesson.index("bursting")


def test_fallback_lesson_uses_the_focus(monkeypatch):
    monkeypatch.setattr(
        tutor_service, "generate_response", lambda prompt: "Made up claim."
    )

    result = grounded_response(
        prompt="p",
        retrieved_knowledge=_evidence(XYLEM, CELL_WALL, XYLEM),
        focus="cell wall",
    )

    assert result.mode == "extractive"
    assert "Cell walls provide shape" in result.text
    assert "Companion cells" not in result.text
