"""assistant memories

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05 19:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('assistant_memories',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('text', sa.String(length=300), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assistant_memories_user_id'), 'assistant_memories', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_assistant_memories_user_id'), table_name='assistant_memories')
    op.drop_table('assistant_memories')
