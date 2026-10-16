"""Join reservation and payment-refund migration histories."""

revision: str = "h20261015_merge_heads_pr96"
down_revision: tuple[str, str] = (
    "h20261012_reservations",
    "h20261013_payment_refunds",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
