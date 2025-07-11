"""update model

Revision ID: 9ffc80419d1d
Revises: 95504b579846
Create Date: 2025-04-17 18:32:50.833314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ffc80419d1d'
down_revision: Union[str, None] = '95504b579846'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
