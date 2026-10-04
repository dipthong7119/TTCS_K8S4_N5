"""Merge migration heads after pull

Revision ID: df03d362bc53
Revises: 9bddb7b0b0a7, h20261002_t20_connector_errors
Create Date: 2026-10-02 22:57:39.921367

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "df03d362bc53"
down_revision: str | None = ("9bddb7b0b0a7", "h20261002_t20_connector_errors")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
