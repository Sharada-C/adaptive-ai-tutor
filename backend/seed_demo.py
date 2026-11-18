"""Seed a demo course so a fresh install is usable straight away.

Creates the "Computer Networks" subject with a small concept graph
(including prerequisites) and ingests the sample study material in
``backend/data`` as subject-wide knowledge.

Run from the ``backend`` directory, after ``python create_tables.py``:

    python seed_demo.py                    # course + knowledge (needs Ollama)
    python seed_demo.py --skip-knowledge   # course only (no Ollama needed)

The script is safe to run more than once.
"""

import argparse
import sys
from pathlib import Path

import requests

from app.db.database import SessionLocal
from app.models.curriculum import Subject
from app.rag.knowledge_ingestion import ingest_text_for_subject
from app.schemas.curriculum_generation import GeneratedCurriculum
from app.services.curriculum_persistence import save_generated_curriculum


DATA_DIR = Path(__file__).resolve().parent / "data"

KNOWLEDGE_FILES = [
    "computer_networks.txt",
    "network_protocols.txt",
]

CURRICULUM = {
    "subject": "Computer Networks",
    "description": (
        "How devices communicate: networks, devices, protocols and "
        "architecture."
    ),
    "concepts": [
        {
            "name": "Network Fundamentals",
            "description": (
                "What a computer network is and why devices are "
                "interconnected."
            ),
            "prerequisites": [],
        },
        {
            "name": "Network Devices",
            "description": (
                "Switches, routers and other hardware that connect "
                "devices and networks."
            ),
            "prerequisites": ["Network Fundamentals"],
        },
        {
            "name": "Network Protocols",
            "description": (
                "The rules that define how devices communicate over a "
                "network."
            ),
            "prerequisites": ["Network Fundamentals"],
        },
        {
            "name": "Network Architecture",
            "description": (
                "How network components are organized, such as "
                "client-server and peer-to-peer."
            ),
            "prerequisites": ["Network Fundamentals"],
        },
        {
            "name": "Transport Protocols",
            "description": "TCP and UDP and how they deliver data.",
            "prerequisites": ["Network Protocols"],
        },
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-knowledge",
        action="store_true",
        help="Create the course only; do not call Ollama to embed material.",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        subject = (
            db.query(Subject)
            .filter(Subject.name == CURRICULUM["subject"])
            .first()
        )

        if subject is None:
            subject = save_generated_curriculum(
                db=db,
                curriculum=GeneratedCurriculum.model_validate(CURRICULUM),
            )
            print(
                f"Created subject '{subject.name}' with "
                f"{len(subject.concepts)} concepts."
            )
        else:
            print(f"Subject '{subject.name}' already exists.")

        if args.skip_knowledge:
            print("Skipped knowledge ingestion.")
            return 0

        try:
            for file_name in KNOWLEDGE_FILES:
                text = (DATA_DIR / file_name).read_text(encoding="utf-8")

                inserted = ingest_text_for_subject(
                    db=db,
                    subject_id=subject.id,
                    text=text,
                    source=file_name,
                    replace_source=True,
                )

                print(f"Ingested {inserted} chunks from {file_name}.")

        except requests.exceptions.RequestException:
            print(
                "Could not reach Ollama to embed the study material.\n"
                "Start Ollama, pull the embedding model "
                "(ollama pull nomic-embed-text) and run this script "
                "again, or use --skip-knowledge.",
                file=sys.stderr,
            )
            return 1

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
