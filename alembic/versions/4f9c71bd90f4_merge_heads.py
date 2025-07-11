"""merge_heads

Revision ID: 4f9c71bd90f4
Revises: add_module_id_to_testcase, fix_execution_details_status
Create Date: 2025-04-15 18:34:40.881889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f9c71bd90f4'
down_revision: Union[str, None] = ('add_module_id_to_testcase', 'fix_execution_details_status')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
