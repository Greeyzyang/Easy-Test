"""update model

Revision ID: 95504b579846
Revises: 063d340a30bb
Create Date: 2025-04-17 11:48:33.145824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95504b579846'
down_revision: Union[str, None] = '063d340a30bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
