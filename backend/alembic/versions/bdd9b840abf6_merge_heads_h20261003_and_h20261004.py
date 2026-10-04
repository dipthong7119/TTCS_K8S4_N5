"""merge heads h20261003 and h20261004

Revision ID: bdd9b840abf6
Revises: h20261003_t21_ocpp_request_payload, h20261004_boot_notification
Create Date: 2026-10-04 10:46:58.705085

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'bdd9b840abf6'
down_revision: str | None = ('h20261003_t21_ocpp_request_payload', 'h20261004_boot_notification')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
