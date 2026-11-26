"""Measure how well retrieval finds the right passage.

Usage (from ``backend``, with Ollama running and the database migrated)::

    python -m app.rag.retrieval_eval

A fixed corpus of short passages (``eval/retrieval_corpus.json``) is embedded
into a temporary course. Each question in ``eval/retrieval_questions.json``
names the passage(s) that answer it, written in different words from the
passage. Questions with an empty ``gold`` list are unanswerable from the
corpus and should be rejected by the similarity threshold.

Reported:
  * Recall@k  - answerable questions with a gold passage in the top k.
  * MRR       - mean reciprocal rank of the first gold passage.
  * Recall@k with the production threshold (what the app really returns).
  * Rejection - unanswerable questions that correctly return nothing.

The temporary course is always removed afterwards.
"""

import json
import sys
import uuid
from pathlib import Path

from app.rag.retriever import (
    DEFAULT_LIMIT,
    DEFAULT_SIMILARITY_THRESHOLD,
    retrieve_relevant_chunks_with_scores,
)

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"
CORPUS_FILE = EVAL_DIR / "retrieval_corpus.json"
QUESTIONS_FILE = EVAL_DIR / "retrieval_questions.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def first_gold_rank(sources: list[str], gold: list[str]) -> int | None:
    """1-based rank of the first gold passage, or None if absent."""

    for position, source in enumerate(sources, start=1):
        if source in gold:
            return position

    return None


def summarise(
    questions: list[dict],
    ranked: list[list[str]],
    limit: int,
) -> dict:
    """Aggregate per-question ranked source lists into metrics."""

    answerable = [
        (q, r) for q, r in zip(questions, ranked, strict=True) if q["gold"]
    ]
    unanswerable = [
        (q, r) for q, r in zip(questions, ranked, strict=True) if not q["gold"]
    ]

    ranks = [first_gold_rank(r, q["gold"]) for q, r in answerable]
    hits = [rank is not None and rank <= limit for rank in ranks]

    total = len(answerable)
    reciprocal = [1 / rank if rank else 0.0 for rank in ranks]

    return {
        "answerable": total,
        f"recall_at_{limit}": (sum(hits) / total) if total else 0.0,
        "top1": (
            sum(1 for rank in ranks if rank == 1) / total if total else 0.0
        ),
        "mrr": (sum(reciprocal) / total) if total else 0.0,
        "misses": [
            {
                "question": q["question"],
                "gold": q["gold"],
                "retrieved": r,
            }
            for (q, r), hit in zip(answerable, hits, strict=True)
            if not hit
        ],
        "unanswerable": len(unanswerable),
        "correctly_rejected": sum(1 for _q, r in unanswerable if not r),
        "wrongly_answered": [
            {"question": q["question"], "retrieved": r}
            for q, r in unanswerable
            if r
        ],
    }


def run(
    db,
    corpus: list[dict],
    questions: list[dict],
    limit: int = DEFAULT_LIMIT,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict:
    """Ingest the corpus into a temporary course, evaluate, then clean up."""

    from app.models.curriculum import Subject
    from app.models.knowledge import KnowledgeChunk
    from app.rag.knowledge_ingestion import ingest_text_for_subject

    subject = Subject(
        name=f"retrieval-eval-{uuid.uuid4().hex[:8]}",
        description="Temporary course for retrieval evaluation.",
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    subject_id = subject.id

    try:
        for passage in corpus:
            ingest_text_for_subject(
                db=db,
                subject_id=subject_id,
                text=passage["text"],
                source=passage["id"],
            )

        def ranked_sources(min_similarity: float) -> list[list[str]]:
            return [
                [
                    hit["source"]
                    for hit in retrieve_relevant_chunks_with_scores(
                        db=db,
                        query=q["question"],
                        subject_id=subject_id,
                        limit=limit,
                        similarity_threshold=min_similarity,
                    )
                ]
                for q in questions
            ]

        return {
            "corpus_passages": len(corpus),
            "questions": len(questions),
            "limit": limit,
            "threshold": threshold,
            "ranking_only": summarise(questions, ranked_sources(0.0), limit),
            "with_threshold": summarise(
                questions, ranked_sources(threshold), limit
            ),
        }

    finally:
        db.rollback()
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.subject_id == subject_id
        ).delete()
        db.query(Subject).filter(Subject.id == subject_id).delete()
        db.commit()


def format_report(report: dict) -> str:
    limit = report["limit"]
    lines = [
        f"Corpus: {report['corpus_passages']} passages, "
        f"{report['questions']} questions, top-{limit}",
    ]

    for key, title in (
        ("ranking_only", "Ranking only (no similarity threshold)"),
        (
            "with_threshold",
            f"As the app runs (similarity >= {report['threshold']})",
        ),
    ):
        part = report[key]
        lines += [
            "",
            title,
            f"  Recall@{limit}: {part[f'recall_at_{limit}']:.0%} "
            f"of {part['answerable']} answerable questions",
            f"  Top-1:      {part['top1']:.0%}",
            f"  MRR:        {part['mrr']:.2f}",
            f"  Unanswerable rejected: {part['correctly_rejected']} "
            f"of {part['unanswerable']}",
        ]

        for miss in part["misses"]:
            lines.append(
                f"  MISS: {miss['question']} "
                f"(wanted {miss['gold']}, got {miss['retrieved']})"
            )

        for wrong in part["wrongly_answered"]:
            lines.append(
                f"  NOT REJECTED: {wrong['question']} "
                f"(got {wrong['retrieved']})"
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from app.db.database import SessionLocal

    corpus = load_json(CORPUS_FILE)
    questions = load_json(QUESTIONS_FILE)

    db = SessionLocal()

    try:
        report = run(db, corpus, questions)
    finally:
        db.close()

    print(format_report(report))

    out = EVAL_DIR / "retrieval_eval.report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
