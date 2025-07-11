"""update model

Revision ID: 9ebfbcc6d5f6
Revises: 3ff434abac9c
Create Date: 2025-04-17 09:45:48.872445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ebfbcc6d5f6'
down_revision: Union[str, None] = '3ff434abac9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
