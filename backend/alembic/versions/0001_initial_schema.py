"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-05 14:56:55.137823
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('match_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('resume_title', sa.String(length=200), nullable=True),
    sa.Column('skills', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('years_experience', sa.Float(), nullable=True),
    sa.Column('job_title', sa.String(length=300), nullable=False),
    sa.Column('job_company', sa.String(length=300), nullable=True),
    sa.Column('job_source', sa.String(length=50), nullable=True),
    sa.Column('relevance_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_match_events_created_at', 'match_events', ['created_at'], unique=False)

    op.create_table('resume_scan_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('skills', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('years_experience', sa.Float(), nullable=True),
    sa.Column('ats_score', sa.Float(), nullable=False),
    sa.Column('formatting_score', sa.Float(), nullable=False),
    sa.Column('content_score', sa.Float(), nullable=False),
    sa.Column('keyword_score', sa.Float(), nullable=False),
    sa.Column('had_job_description', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_resume_scan_events_created_at', 'resume_scan_events', ['created_at'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table('resumes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('document', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('target_job_description', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('last_score', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_resumes_user_id', 'resumes', ['user_id'], unique=False)

    op.create_table('scans',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('resume_id', sa.String(length=36), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=True),
    sa.Column('ats_score', sa.Float(), nullable=False),
    sa.Column('formatting_score', sa.Float(), nullable=False),
    sa.Column('content_score', sa.Float(), nullable=False),
    sa.Column('keyword_score', sa.Float(), nullable=False),
    sa.Column('had_job_description', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scans_created_at', 'scans', ['created_at'], unique=False)
    op.create_index('ix_scans_resume_id', 'scans', ['resume_id'], unique=False)
    op.create_index('ix_scans_user_id', 'scans', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scans_user_id', table_name='scans')
    op.drop_index('ix_scans_resume_id', table_name='scans')
    op.drop_index('ix_scans_created_at', table_name='scans')

    op.drop_table('scans')
    op.drop_index('ix_resumes_user_id', table_name='resumes')

    op.drop_table('resumes')
    op.drop_index('ix_users_email', table_name='users')

    op.drop_table('users')
    op.drop_index('ix_resume_scan_events_created_at', table_name='resume_scan_events')

    op.drop_table('resume_scan_events')
    op.drop_index('ix_match_events_created_at', table_name='match_events')

    op.drop_table('match_events')
