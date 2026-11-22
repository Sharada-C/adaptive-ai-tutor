"""baseline schema

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-11-21

"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the original schema (before auth columns and the subject index)."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('subjects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('concepts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('student_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('learning_level', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('assessment_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('student_answer', sa.Text(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('result', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('concept_mastery',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('mastery_score', sa.Float(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('correct_answers', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('concept_prerequisites',
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('prerequisite_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['prerequisite_id'], ['concepts.id'], ),
    sa.PrimaryKeyConstraint('concept_id', 'prerequisite_id')
    )
    op.create_table('diagnostic_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id'], ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('knowledge_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=True),
    sa.Column('subject_id', sa.Integer(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('source', sa.String(length=255), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_chunks_concept_id'), 'knowledge_chunks', ['concept_id'], unique=False)
    op.create_table('misconceptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('resolved', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['student_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('diagnostic_questions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('expected_answer', sa.Text(), nullable=False),
    sa.Column('evaluation_criteria', sa.Text(), nullable=False),
    sa.Column('misconception_guidance', sa.Text(), nullable=True),
    sa.Column('student_answer', sa.Text(), nullable=True),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('result', sa.String(length=30), nullable=True),
    sa.Column('answered', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['diagnostic_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('diagnostic_questions')
    op.drop_table('misconceptions')
    op.drop_index(op.f('ix_knowledge_chunks_concept_id'), table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.drop_table('diagnostic_sessions')
    op.drop_table('concept_prerequisites')
    op.drop_table('concept_mastery')
    op.drop_table('assessment_attempts')
    op.drop_table('student_profiles')
    op.drop_table('concepts')
    op.drop_table('users')
    op.drop_table('subjects')
