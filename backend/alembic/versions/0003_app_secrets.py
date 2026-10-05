"""app secrets (server-generated JWT signing key)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05 16:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('app_secrets',
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('value', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('name')
    )


def downgrade() -> None:
    op.drop_table('app_secrets')
