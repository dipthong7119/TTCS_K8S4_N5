"""S-52: bảng reservations tối thiểu + cột no_show_fee_vnd cho stations
+ mở rộng CheckConstraint wallet_ledger để chấp nhận entry_type = no_show_fee.

Tiến: tạo bảng reservations, thêm cột stations.no_show_fee_vnd,
      cập nhật ck_wallet_ledger_amount_sign cho loại mới.
Lùi: xoá bảng, xoá cột, khôi phục constraint cũ (nếu không có dữ liệu no_show_fee).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261014_reservations"
down_revision: str = "h20261013_payment_refunds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Thêm cột phí không đến vào stations (dùng batch vì SQLite)
    with op.batch_alter_table("stations") as batch:
        batch.add_column(
            sa.Column(
                "no_show_fee_vnd",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.create_check_constraint(
            "ck_stations_no_show_fee_nonneg",
            "no_show_fee_vnd >= 0",
        )

    # 2. Tạo bảng reservations
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_user_id", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("id_tag_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expiry_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("fulfilled_session_id", sa.Integer(), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(), nullable=True),
        sa.Column("expired_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("no_show_fee_vnd", sa.Integer(), nullable=True),
        sa.Column("fee_ledger_entry_id", sa.Integer(), nullable=True),
        sa.Column("fee_waived_reason", sa.String(length=200), nullable=True),
        sa.Column("cancel_status", sa.String(length=20), nullable=False),
        sa.Column("cancel_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_cancel_attempt_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'fulfilled', 'expired', 'cancelled')",
            name="ck_reservation_status",
        ),
        sa.CheckConstraint(
            "cancel_status IN ('not_needed', 'pending', 'done', 'gone', 'abandoned')",
            name="ck_reservation_cancel_status",
        ),
        sa.CheckConstraint(
            "no_show_fee_vnd IS NULL OR no_show_fee_vnd >= 0",
            name="ck_reservation_fee_nonneg",
        ),
        sa.CheckConstraint(
            "cancel_attempts >= 0",
            name="ck_reservation_cancel_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["driver_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"], ["connectors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["id_tag_id"], ["id_tags.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fulfilled_session_id"],
            ["charging_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reservations_status_expiry",
        "reservations",
        ["status", "expiry_at"],
    )
    op.create_index(
        "ix_reservations_connector_status",
        "reservations",
        ["connector_id", "status"],
    )
    op.create_index(
        "ix_reservations_driver_status",
        "reservations",
        ["driver_user_id", "status"],
    )

    # 3. Mở rộng CheckConstraint wallet_ledger để chấp nhận no_show_fee
    #    (SQLite không hỗ trợ ALTER COLUMN → dùng batch_alter_table)
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge', 'payment_refund', 'no_show_fee') AND amount_vnd < 0)",
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Chặn lùi nếu đã có dữ liệu no_show_fee trong sổ cái
    has_no_show = bind.execute(
        sa.text("SELECT 1 FROM wallet_ledger WHERE entry_type = 'no_show_fee' LIMIT 1")
    ).first()
    if has_no_show:
        raise RuntimeError(
            "Có bút toán no_show_fee trong wallet_ledger; "
            "cần forward migration để xoá dữ liệu trước khi downgrade"
        )

    # Khôi phục constraint wallet_ledger
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge', 'payment_refund') AND amount_vnd < 0)",
        )

    # Xoá chỉ mục và bảng reservations
    op.drop_index("ix_reservations_driver_status", table_name="reservations")
    op.drop_index("ix_reservations_connector_status", table_name="reservations")
    op.drop_index("ix_reservations_status_expiry", table_name="reservations")
    op.drop_table("reservations")

    # Xoá cột và constraint của stations
    with op.batch_alter_table("stations") as batch:
        batch.drop_constraint("ck_stations_no_show_fee_nonneg", type_="check")
        batch.drop_column("no_show_fee_vnd")
