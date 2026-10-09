"""Merge multiple heads

Revision ID: e97a880b36e9
Revises: h20261009_wallet_types, h20261010_tariffs_config
Create Date: 2026-10-10 01:47:10.922853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e97a880b36e9'
down_revision: Union[str, None] = ('h20261009_wallet_types', 'h20261010_tariffs_config')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
