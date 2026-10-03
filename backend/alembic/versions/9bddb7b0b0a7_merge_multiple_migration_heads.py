"""Merge multiple migration heads

Revision ID: 9bddb7b0b0a7
Revises: g12h34i56j78, h20261002_t19_status
Create Date: 2026-10-02 21:56:59.573418

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '9bddb7b0b0a7'
down_revision: str | None = ('g12h34i56j78', 'h20261002_t19_status')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
