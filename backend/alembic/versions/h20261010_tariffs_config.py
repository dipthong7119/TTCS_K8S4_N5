"""SCRUM-61/204/205: join tariff and configuration/payment migrations."""

from collections.abc import Sequence

revision: str = "h20261010_tariffs_config"
down_revision: tuple[str, ...] = (
    "h20261010_config_payments",
    "h20261009_invoice_rounding",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
