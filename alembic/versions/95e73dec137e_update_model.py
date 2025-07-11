"""update_model

Revision ID: 95e73dec137e
Revises: 3b9ee63eb7c5
Create Date: 2025-03-27 11:55:53.146138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '95e73dec137e'
down_revision: Union[str, None] = '3b9ee63eb7c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 删除或注释掉添加 module_id 的代码
    # op.add_column('testcases', sa.Column('module_id', sa.CHAR(36), nullable=True))
    pass

def downgrade():
    # 如果需要回滚，可以保留删除列的代码
    op.drop_column('testcases', 'module_id')
    op.create_table('user',
    sa.Column('id', mysql.CHAR(length=36), nullable=False),
    sa.Column('email', mysql.VARCHAR(length=320), nullable=False),
    sa.Column('hashed_password', mysql.VARCHAR(length=1024), nullable=False),
    sa.Column('is_active', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
    sa.Column('is_superuser', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
    sa.Column('is_verified', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_user_email', 'user', ['email'], unique=True)
    # ### end Alembic commands ###
