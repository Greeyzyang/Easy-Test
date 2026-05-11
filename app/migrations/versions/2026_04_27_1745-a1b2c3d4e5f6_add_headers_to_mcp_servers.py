"""add headers column to mcp_servers

Revision ID: a1b2c3d4e5f6
Revises: 8676e4ecc972
Create Date: 2026-04-27 17:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '8676e4ecc972'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mcp_servers', sa.Column('headers', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('mcp_servers', 'headers')
