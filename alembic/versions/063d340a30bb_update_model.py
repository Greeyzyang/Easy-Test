"""update model

Revision ID: 063d340a30bb
Revises: 9ebfbcc6d5f6
Create Date: 2025-04-17 09:51:29.423839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '063d340a30bb'
down_revision: Union[str, None] = '9ebfbcc6d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
