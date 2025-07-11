"""update model

Revision ID: 1abc8ec4f3cb
Revises: 9ffc80419d1d
Create Date: 2025-04-21 12:42:24.900548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1abc8ec4f3cb'
down_revision: Union[str, None] = '9ffc80419d1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
