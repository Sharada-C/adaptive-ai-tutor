from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.knowledge import KnowledgeChunk
from app.rag.embedding_service import generate_embedding


KNOWLEDGE = [
    {
        "concept_id": 1,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "A program is a passive set of instructions stored on secondary "
            "storage such as a disk. A process is a program that is currently "
            "executing. A process has its own execution state and uses system "
            "resources such as CPU time and memory."
        ),
    },
    {
        "concept_id": 1,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "Process management is the operating system activity concerned "
            "with creating, scheduling, synchronizing, and terminating "
            "processes. The operating system manages process states and "
            "allocates resources needed for execution."
        ),
    },
    {
        "concept_id": 1,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "A process can move through states such as new, ready, running, "
            "waiting, and terminated. A process in the ready state is waiting "
            "for the CPU. A process in the waiting state is waiting for an "
            "event such as completion of an I/O operation."
        ),
    },
    {
        "concept_id": 2,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "Process scheduling determines which ready process should receive "
            "CPU time. The scheduler selects processes from the ready queue "
            "and determines their execution order according to the scheduling "
            "algorithm and scheduling policy."
        ),
    },
    {
        "concept_id": 2,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "Common CPU scheduling algorithms include First-Come, First-Served "
            "(FCFS), Shortest Job First (SJF), Round Robin, and Priority "
            "Scheduling. Different algorithms make different trade-offs "
            "between waiting time, response time, turnaround time, and fairness."
        ),
    },
    {
        "concept_id": 2,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "When a running process blocks for I/O, it cannot continue using "
            "the CPU. The operating system can schedule another ready process "
            "while the first process waits for the I/O operation to complete."
        ),
    },
    {
        "concept_id": 3,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "A thread is a unit of execution within a process. Threads belonging "
            "to the same process share the process's address space and many "
            "resources, while each thread has its own execution state and "
            "stack."
        ),
    },
    {
        "concept_id": 4,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "Process synchronization coordinates concurrent processes or "
            "threads when they access shared resources. Synchronization "
            "mechanisms help prevent race conditions and maintain consistency "
            "when multiple execution flows interact with shared data."
        ),
    },
    {
        "concept_id": 5,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "Memory management is the operating system function responsible "
            "for managing main memory. It tracks memory usage, allocates memory "
            "to processes, and reclaims memory when it is no longer needed."
        ),
    },
    {
        "concept_id": 6,
        "source": "Adaptive AI Tutor - Operating Systems",
        "content": (
            "Virtual memory allows a system to provide processes with an "
            "address space larger than the available physical memory by using "
            "secondary storage as part of the memory-management mechanism. "
            "It enables processes to run without requiring all of their data "
            "to be in physical memory at the same time."
        ),
    },
]


def ingest_knowledge() -> None:
    db: Session = SessionLocal()

    try:
        # Make ingestion idempotent for this prototype.
        db.query(KnowledgeChunk).delete()

        for item in KNOWLEDGE:
            embedding = generate_embedding(item["content"])

            chunk = KnowledgeChunk(
                concept_id=item["concept_id"],
                content=item["content"],
                source=item["source"],
                embedding=embedding,
            )

            db.add(chunk)

        db.commit()

        print(
            f"Inserted {len(KNOWLEDGE)} knowledge chunks successfully."
        )

    finally:
        db.close()


if __name__ == "__main__":
    ingest_knowledge()

