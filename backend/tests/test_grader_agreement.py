import json

import pytest

from app.tutor import grader_agreement as ga


def _examples(tmp_path, rows):
    path = tmp_path / "ex.json"
    path.write_text(json.dumps(rows))
    return path


def _row(label, answer="a"):
    return {"question": "q", "expected_answer": "e", "student_answer": answer, "label": label}


def test_shipped_examples_are_valid_and_balanced():
    examples = ga.load_examples(ga.DEFAULT_FILE)

    labels = {e["label"] for e in examples}
    assert {"correct", "incorrect"} <= labels
    assert len(examples) >= 10


def test_measure_counts_agreement_and_both_kinds_of_error():
    rows = [
        _row("correct", "good"),          # graded correct   -> agrees
        _row("correct", "wrongly-failed"),  # graded incorrect -> false reject
        _row("incorrect", "good-fail"),   # graded incorrect -> agrees
        _row("incorrect", "wrongly-passed"),  # graded correct -> false credit
    ]
    graded = {
        "good": "correct",
        "wrongly-failed": "incorrect",
        "good-fail": "incorrect",
        "wrongly-passed": "correct",
    }

    report = ga.measure(rows, lambda q, e, a: {"result": graded[a], "score": 0.0})

    assert report["total"] == 4
    assert report["agreement"] == 0.5
    assert report["false_reject"] == 1 and report["should_pass"] == 2
    assert report["false_credit"] == 1 and report["should_fail"] == 2


def test_partially_correct_maps_to_partial():
    report = ga.measure(
        [_row("partial")], lambda q, e, a: {"result": "partially_correct", "score": 0.5}
    )

    assert report["agreement"] == 1.0


def test_a_crashing_grade_counts_as_a_failure(tmp_path):
    def boom(q, e, a):
        raise RuntimeError("ollama down")

    report = ga.measure([_row("correct")], boom)

    assert report["agreement"] == 0.0
    assert report["rows"][0]["predicted"] == "error"
    assert "ollama down" in report["rows"][0]["feedback"]


def test_invalid_labels_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        ga.load_examples(_examples(tmp_path, [_row("maybe")]))


def test_report_lists_disagreements():
    report = ga.measure([_row("correct", "x")], lambda q, e, a: {"result": "incorrect", "score": 0})

    text = ga.format_report(report)

    assert "Disagreements (1)" in text and "correct -> incorrect" in text
