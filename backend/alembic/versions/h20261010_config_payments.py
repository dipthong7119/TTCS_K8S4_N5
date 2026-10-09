"""SCRUM-60: join configuration and payment migration histories."""

from collections.abc import Sequence

revision: str = "h20261010_config_payments"
down_revision: tuple[str, ...] = (
    "h20261009_charge_point_configuration",
    "h20261009_payment_transactions",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
