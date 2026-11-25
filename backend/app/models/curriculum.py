from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


concept_prerequisites = Table(
    "concept_prerequisites",
    Base.metadata,
    Column(
        "concept_id",
        ForeignKey("concepts.id"),
        primary_key=True,
    ),
    Column(
        "prerequisite_id",
        ForeignKey("concepts.id"),
        primary_key=True,
    ),
)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # NULL = shared course made by staff; set = private to that student.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Shared course names are globally unique; a private name only has
        # to be unique within its owner, so two students can both study
        # "Binary Search".
        Index(
            "uq_subjects_shared_name",
            "name",
            unique=True,
            postgresql_where=text("owner_id IS NULL"),
        ),
        UniqueConstraint("owner_id", "name", name="uq_subjects_owner_name"),
    )

    @property
    def is_private(self) -> bool:
        return self.owner_id is not None


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True)

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    subject: Mapped["Subject"] = relationship(
        back_populates="concepts"
    )

    prerequisites: Mapped[list["Concept"]] = relationship(
        secondary=concept_prerequisites,
        primaryjoin=id == concept_prerequisites.c.concept_id,
        secondaryjoin=id == concept_prerequisites.c.prerequisite_id,
        backref="dependent_concepts",
    )