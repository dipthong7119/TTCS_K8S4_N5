"""Compatibility marker for local databases carrying the earlier merge stamp.

Some local Postgres volumes were migrated with this revision id before the
merge migration was checked in. Its observed schema contains the S-48
reservation table and station power allocation. Keep the id in the graph so
Alembic can upgrade those volumes without resetting their data.
"""

from collections.abc import Sequence

revision: str = "h20261015_merge_resv_heads"
down_revision: tuple[str, str] = (
    "h20261015_merge_heads_pr96",
    "h20261014_station_power_allocation",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
