"""add load_tests and load_test_reports tables

Revision ID: 1a2b3c4d5e6f
Revises: 8676e4ecc972
Create Date: 2026-04-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '1a2b3c4d5e6f'
down_revision = '8676e4ecc972'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # load_tests table
    op.create_table(
        'load_tests',
        sa.Column('id', mysql.CHAR(collation='utf8mb4_unicode_ci', length=36), nullable=False),
        sa.Column('name', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255), nullable=False),
        sa.Column('description', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255), nullable=True),
        sa.Column('project_id', mysql.CHAR(collation='utf8mb4_unicode_ci', length=36), nullable=False),
        sa.Column('status', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=50), nullable=True),
        sa.Column('concurrent_users', mysql.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('duration_seconds', mysql.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('ramp_up_seconds', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('target_base_url', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=500), nullable=True),
        sa.Column('request_config', mysql.JSON(), nullable=True),
        sa.Column('created_by', mysql.CHAR(collation='utf8mb4_unicode_ci', length=36), nullable=True),
        sa.Column('created_time', mysql.DATETIME(), nullable=True),
        sa.Column('updated_time', mysql.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='load_tests_ibfk_1'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='load_tests_ibfk_2'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_unicode_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB'
    )
    op.create_index(op.f('ix_load_tests_name'), 'load_tests', ['name'], unique=False)

    # load_test_reports table
    op.create_table(
        'load_test_reports',
        sa.Column('id', mysql.CHAR(collation='utf8mb4_unicode_ci', length=36), nullable=False),
        sa.Column('load_test_id', mysql.CHAR(collation='utf8mb4_unicode_ci', length=36), nullable=False),
        sa.Column('status', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=50), nullable=True),
        sa.Column('start_time', mysql.DATETIME(), nullable=True),
        sa.Column('end_time', mysql.DATETIME(), nullable=True),
        sa.Column('duration_seconds', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('total_requests', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('successful_requests', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('failed_requests', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('error_rate', mysql.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('avg_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('min_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('max_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('median_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('p90_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('p95_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('p99_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('stddev_response_time', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('requests_per_second', mysql.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('timeline_data', mysql.JSON(), nullable=True),
        sa.Column('scenario_stats', mysql.JSON(), nullable=True),
        sa.Column('created_time', mysql.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['load_test_id'], ['load_tests.id'], name='load_test_reports_ibfk_1', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_unicode_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB'
    )


def downgrade() -> None:
    op.drop_table('load_test_reports')
    op.drop_index(op.f('ix_load_tests_name'), table_name='load_tests')
    op.drop_table('load_tests')
