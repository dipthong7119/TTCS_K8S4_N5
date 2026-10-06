"""T-01: merge the OCPP payload and BootNotification migration branches."""

from collections.abc import Sequence

revision: str = "h20261004_merge_boot"
down_revision: tuple[str, str] = (
    "h20261003_t21_request_payload",
    "h20261004_boot_notification",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
