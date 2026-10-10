"""Merge multiple heads

Revision ID: e97a880b36e9
Revises: h20261009_wallet_types, h20261010_tariffs_config
Create Date: 2026-10-10 01:47:10.922853

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'e97a880b36e9'
down_revision: str | None = ('h20261009_wallet_types', 'h20261010_tariffs_config')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
