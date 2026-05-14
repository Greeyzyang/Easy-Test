"""add_indexes_to_foreign_keys_and_status_columns

Revision ID: 42c1a83499b8
Revises: 19bfe431b934
Create Date: 2026-05-12 17:58:23.387559

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '42c1a83499b8'
down_revision = '19bfe431b934'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All foreign key indexes and status indexes already exist in the database.
    # Only add the missing status index on load_test_reports.
    op.create_index('ix_load_test_reports_status', 'load_test_reports', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_load_test_reports_status', table_name='load_test_reports')
