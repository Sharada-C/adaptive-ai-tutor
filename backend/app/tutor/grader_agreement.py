"""Measure how often the grader agrees with human labels.

Run from the ``backend`` folder with Ollama running::

    python -m app.tutor.grader_agreement
    python -m app.tutor.grader_agreement eval/my_labels.json

Set ``GRADER_MODEL`` (e.g. ``qwen2.5:7b``) in ``.env`` or the environment to
compare models. Each example is graded by the real ``evaluate_answer``.
"""

import json
import sys
from collections import Counter
from pathlib import Path

LABELS = ("correct", "partial", "incorrect")
RESULT_TO_LABEL = {
    "correct": "correct",
    "partially_correct": "partial",
    "incorrect": "incorrect",
}
DEFAULT_FILE = Path(__file__).resolve().parents[2] / "eval" / "grader_examples.json"


def load_examples(path: Path) -> list[dict]:
    examples = json.loads(Path(path).read_text(encoding="utf-8"))

    for index, item in enumerate(examples, 1):
        missing = {"question", "expected_answer", "student_answer", "label"} - set(item)

        if missing or item["label"] not in LABELS:
            raise ValueError(f"Example {index} is invalid: {sorted(missing) or item['label']}")

    return examples


def measure(examples: list[dict], grade) -> dict:
    """Grade every example with ``grade(question, expected, answer) -> dict``."""

    rows = []

    for item in examples:
        try:
            outcome = grade(item["question"], item["expected_answer"], item["student_answer"])
            predicted = RESULT_TO_LABEL.get(outcome["result"], "incorrect")
        except Exception as error:  # a grading crash is a failure, not a skip
            outcome = {"score": None, "feedback": f"ERROR: {error}"}
            predicted = "error"

        rows.append({**item, "predicted": predicted, "score": outcome.get("score"),
                     "feedback": outcome.get("feedback", "")})

    total = len(rows)
    agree = sum(1 for r in rows if r["predicted"] == r["label"])
    should_pass = [r for r in rows if r["label"] == "correct"]
    should_fail = [r for r in rows if r["label"] == "incorrect"]

    return {
        "total": total,
        "agreement": agree / total if total else 0.0,
        # a wrong answer graded correct (the tutor teaches the student a falsehood)
        "false_credit": sum(1 for r in should_fail if r["predicted"] == "correct"),
        "should_fail": len(should_fail),
        # a correct answer graded incorrect (the bug seen in the diagnostic)
        "false_reject": sum(1 for r in should_pass if r["predicted"] == "incorrect"),
        "should_pass": len(should_pass),
        "confusion": Counter((r["label"], r["predicted"]) for r in rows),
        "rows": rows,
    }


def format_report(report: dict) -> str:
    lines = [
        f"Examples: {report['total']}",
        f"Agreement with your labels: {report['agreement']:.0%}",
        f"Correct answers graded incorrect: {report['false_reject']} of {report['should_pass']}",
        f"Wrong answers graded correct:     {report['false_credit']} of {report['should_fail']}",
        "",
        "labelled -> graded (count)",
    ]

    for (label, predicted), count in sorted(report["confusion"].items()):
        lines.append(f"  {label:9} -> {predicted:9} {count}")

    misses = [r for r in report["rows"] if r["predicted"] != r["label"]]
    lines += ["", f"Disagreements ({len(misses)}):"]

    for r in misses:
        lines.append(f"  [{r['label']} -> {r['predicted']}] {r['student_answer'][:90]}")

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    from app.core.config import settings
    from app.tutor.evaluation_service import evaluate_answer

    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_FILE
    examples = load_examples(path)

    print(f"Grader model: {settings.grader_model or settings.llm_model}")

    report = measure(
        examples,
        lambda q, e, a: evaluate_answer(question=q, expected_answer=e, student_answer=a),
    )

    print(format_report(report))

    out = path.with_suffix(".report.json")
    out.write_text(
        json.dumps({k: v for k, v in report.items() if k != "confusion"}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nFull report: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
