"""job board

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05 15:37:41.418453
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('jobs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source', sa.String(length=30), nullable=False),
    sa.Column('external_id', sa.String(length=500), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('company', sa.String(length=300), nullable=False),
    sa.Column('location', sa.String(length=200), nullable=False),
    sa.Column('discipline', sa.String(length=20), nullable=False),
    sa.Column('employment_type', sa.String(length=20), nullable=False),
    sa.Column('workplace', sa.String(length=20), nullable=False),
    sa.Column('experience_min', sa.Float(), nullable=True),
    sa.Column('experience_max', sa.Float(), nullable=True),
    sa.Column('salary_min', sa.Integer(), nullable=True),
    sa.Column('salary_max', sa.Integer(), nullable=True),
    sa.Column('salary_currency', sa.String(length=3), nullable=False),
    sa.Column('salary_period', sa.String(length=10), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('skills', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('apply_url', sa.String(length=500), nullable=False),
    sa.Column('deadline', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'external_id', name='uq_jobs_source_external_id')
    )
    op.create_index('ix_jobs_created_at', 'jobs', ['created_at'], unique=False)
    op.create_index('ix_jobs_deadline', 'jobs', ['deadline'], unique=False)
    op.create_index('ix_jobs_source', 'jobs', ['source'], unique=False)
    op.create_index('ix_jobs_status_discipline', 'jobs', ['status', 'discipline'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jobs_status_discipline', table_name='jobs')
    op.drop_index('ix_jobs_source', table_name='jobs')
    op.drop_index('ix_jobs_deadline', table_name='jobs')
    op.drop_index('ix_jobs_created_at', table_name='jobs')
    op.drop_table('jobs')
