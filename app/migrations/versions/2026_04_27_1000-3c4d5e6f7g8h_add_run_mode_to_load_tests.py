"""add run_mode and total_requests_limit to load_tests

Revision ID: 3c4d5e6f7g8h
Revises: 2b3c4d5e6f7g
Create Date: 2026-04-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '3c4d5e6f7g8h'
down_revision = '2b3c4d5e6f7g'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('load_tests', sa.Column('run_mode', sa.String(length=20), nullable=True))
    op.add_column('load_tests', sa.Column('total_requests_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('load_tests', 'total_requests_limit')
    op.drop_column('load_tests', 'run_mode')
