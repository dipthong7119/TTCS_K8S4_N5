"""Join existing subscription and tariff migration heads before S-24."""

from collections.abc import Sequence

revision: str = "h20261011_merge_heads"
down_revision: tuple[str, ...] = ("6a9fa9862b72", "h20261010_tariffs_config")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
