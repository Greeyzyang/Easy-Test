"""remove_interface_module_relationship

Revision ID: 3ff434abac9c
Revises: 6437fdd73900
Create Date: 2025-04-16 16:12:29.413827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ff434abac9c'
down_revision: Union[str, None] = '6437fdd73900'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
