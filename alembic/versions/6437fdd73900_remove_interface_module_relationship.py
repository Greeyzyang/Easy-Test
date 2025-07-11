"""remove_interface_module_relationship

Revision ID: 6437fdd73900
Revises: e235d0fcabd9
Create Date: 2025-04-16 13:03:25.656026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6437fdd73900'
down_revision: Union[str, None] = 'e235d0fcabd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
