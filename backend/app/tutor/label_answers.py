"""Label student answers by hand so the grader can be measured against you.

Run from the ``backend`` folder::

    python -m app.tutor.label_answers
    python -m app.tutor.label_answers eval/grader_holdout_to_label.json

It shows each question, the reference answer and one student answer, and asks
for your verdict. Progress is saved after every answer, so you can stop and
continue later. By default the verdicts go to ``eval/grader_labels.json``;
for another file the name is derived (``x_to_label.json`` -> ``x_labels.json``).
``grader_agreement`` reads the labels file.

Judge each answer against the reference answer:

  c  correct    - gets the key idea(s) right; paraphrase, shorter wording,
                  informal language or extra true detail are fine
  p  partial    - gets part of it right but misses or blurs something essential
                  or mixes right and wrong
  i  incorrect  - wrong, contradicts the reference, off-topic or empty
  s  skip       - decide later        q  quit and save
"""

import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
SOURCE = EVAL_DIR / "grader_to_label.json"
TARGET = EVAL_DIR / "grader_labels.json"

CHOICES = {"c": "correct", "p": "partial", "i": "incorrect"}


def load_progress(source: Path, target: Path) -> list[dict]:
    """Source examples, with any labels already saved in ``target`` applied."""

    examples = json.loads(source.read_text(encoding="utf-8"))
    saved = {}

    if target.exists():
        for item in json.loads(target.read_text(encoding="utf-8")):
            saved[(item["question"], item["student_answer"])] = item["label"]

    for item in examples:
        item["label"] = saved.get((item["question"], item["student_answer"]), "")

    return examples


def save_progress(examples: list[dict], target: Path) -> None:
    labelled = [item for item in examples if item["label"] in CHOICES.values()]
    target.write_text(
        json.dumps(labelled, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run(source: Path = SOURCE, target: Path = TARGET, ask=None, show=print) -> int:
    ask = ask or input
    examples = load_progress(source, target)
    todo = [item for item in examples if not item["label"]]

    show(__doc__)
    show(f"{len(examples) - len(todo)} labelled, {len(todo)} to go.\n")

    for number, item in enumerate(todo, 1):
        show("-" * 70)
        show(f"[{number}/{len(todo)}] QUESTION:  {item['question']}")
        show(f"REFERENCE:  {item['expected_answer']}")
        show(f"STUDENT:    {item['student_answer']}")

        while True:
            choice = ask("c / p / i / s / q > ").strip().lower()

            if choice in CHOICES:
                item["label"] = CHOICES[choice]
                save_progress(examples, target)
                break

            if choice == "s":
                break

            if choice == "q":
                save_progress(examples, target)
                show("Saved. Run the command again to continue.")
                return sum(1 for e in examples if e["label"])

            show("Type c, p, i, s or q.")

    total = sum(1 for e in examples if e["label"])
    show(f"\nDone: {total} labelled -> {target.name}")

    return total


if __name__ == "__main__":
    run()


def default_target(source: Path) -> Path:
    if source == SOURCE:
        return TARGET

    return source.with_name(source.stem.replace("_to_label", "") + "_labels.json")


def main(argv: list[str] | None = None) -> int:
    """Optional arguments: the file to label, then the file to save to."""

    args = sys.argv[1:] if argv is None else argv
    source = Path(args[0]) if args else SOURCE
    target = Path(args[1]) if len(args) > 1 else default_target(source)

    return run(source, target)


if __name__ == "__main__":
    main()
