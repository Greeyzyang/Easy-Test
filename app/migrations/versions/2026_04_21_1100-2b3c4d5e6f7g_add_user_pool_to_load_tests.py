"""add user_pool fields to load_tests

Revision ID: 2b3c4d5e6f7g
Revises: 1a2b3c4d5e6f
Create Date: 2026-04-21 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '2b3c4d5e6f7g'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('load_tests', sa.Column('user_pool_ref', sa.String(length=255), nullable=True))
    op.add_column('load_tests', sa.Column('user_pool_mode', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('load_tests', 'user_pool_mode')
    op.drop_column('load_tests', 'user_pool_ref')
