"""Store versioned partner revenue-share contracts (SCRUM-86).

Revision ID: h20261020_scrum86_revenue_share_contracts
Revises: h20261019_scrum83_power_bands
Create Date: 2026-10-20 00:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "h20261020_scrum86_revenue_share_contracts"
down_revision: str | None = "h20261019_scrum83_power_bands"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("revenue_share_contracts"):
        op.create_table(
            "revenue_share_contracts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "station_owner_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("partner_share_percent", sa.Numeric(5, 2), nullable=False),
            sa.Column("platform_share_percent", sa.Numeric(5, 2), nullable=False),
            sa.Column("effective_from", sa.DateTime(), nullable=False),
            sa.Column("effective_to", sa.DateTime(), nullable=True),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "partner_share_percent >= 0 AND partner_share_percent <= 100",
                name="ck_revenue_share_contract_partner_percent",
            ),
            sa.CheckConstraint(
                "platform_share_percent >= 0 AND platform_share_percent <= 100",
                name="ck_revenue_share_contract_platform_percent",
            ),
            sa.CheckConstraint(
                "partner_share_percent + platform_share_percent = 100",
                name="ck_revenue_share_contract_total_percent",
            ),
            sa.CheckConstraint(
                "effective_to IS NULL OR effective_to > effective_from",
                name="ck_revenue_share_contract_effective_range",
            ),
            sa.UniqueConstraint(
                "station_owner_id",
                "effective_from",
                name="uq_revenue_share_owner_effective",
            ),
        )
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("revenue_share_contracts")}
    if "ix_revenue_share_owner_effective" not in indexes:
        op.create_index(
            "ix_revenue_share_owner_effective",
            "revenue_share_contracts",
            ["station_owner_id", "effective_from", "effective_to"],
        )

    # Preserve the existing 60/40 policy for partners already receiving a share.
    owner_ids = bind.execute(sa.text("SELECT DISTINCT owner_id FROM stations ORDER BY owner_id"))
    rows = [
        {
            "station_owner_id": owner_id,
            "partner_share_percent": 60,
            "platform_share_percent": 40,
            "effective_from": datetime(1970, 1, 1, tzinfo=UTC).replace(tzinfo=None),
        }
        for (owner_id,) in owner_ids
    ]
    if rows:
        op.bulk_insert(
            sa.table(
                "revenue_share_contracts",
                sa.column("station_owner_id", sa.Integer()),
                sa.column("partner_share_percent", sa.Numeric(5, 2)),
                sa.column("platform_share_percent", sa.Numeric(5, 2)),
                sa.column("effective_from", sa.DateTime()),
            ),
            rows,
        )


def downgrade() -> None:
    op.drop_index("ix_revenue_share_owner_effective", table_name="revenue_share_contracts")
    op.drop_table("revenue_share_contracts")
