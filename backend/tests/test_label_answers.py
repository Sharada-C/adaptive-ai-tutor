import json

from app.tutor import grader_agreement, label_answers

EXAMPLES = [
    {"question": "Q1", "expected_answer": "E1", "student_answer": "A1"},
    {"question": "Q1", "expected_answer": "E1", "student_answer": "A2"},
    {"question": "Q2", "expected_answer": "E2", "student_answer": "A3"},
]


def _files(tmp_path):
    source = tmp_path / "to_label.json"
    source.write_text(json.dumps(EXAMPLES))
    return source, tmp_path / "labels.json"


def _answers(*replies):
    queue = iter(replies)
    return lambda prompt: next(queue)


def test_labels_are_saved_and_readable_by_the_agreement_tool(tmp_path):
    source, target = _files(tmp_path)

    label_answers.run(source, target, ask=_answers("c", "p", "i"), show=lambda *_: None)

    examples = grader_agreement.load_examples(target)

    assert [e["label"] for e in examples] == ["correct", "partial", "incorrect"]


def test_quitting_saves_and_resuming_continues(tmp_path):
    source, target = _files(tmp_path)

    label_answers.run(source, target, ask=_answers("c", "q"), show=lambda *_: None)
    assert len(json.loads(target.read_text())) == 1

    label_answers.run(source, target, ask=_answers("i", "p"), show=lambda *_: None)

    labels = [e["label"] for e in json.loads(target.read_text())]
    assert labels == ["correct", "incorrect", "partial"]


def test_skipped_and_invalid_input_are_not_saved_as_labels(tmp_path):
    source, target = _files(tmp_path)

    label_answers.run(
        source, target, ask=_answers("x", "s", "c", "s"), show=lambda *_: None
    )

    assert [e["label"] for e in json.loads(target.read_text())] == ["correct"]


def test_main_derives_the_labels_file_name_from_the_source(tmp_path, monkeypatch):
    source = tmp_path / "grader_holdout_to_label.json"
    source.write_text(json.dumps(EXAMPLES))
    monkeypatch.setattr("builtins.input", _answers("c", "c", "c"))

    label_answers.main([str(source)])

    assert (tmp_path / "grader_holdout_labels.json").exists()
