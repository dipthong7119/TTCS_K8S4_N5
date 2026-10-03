"""T-16: đảm bảo charge_points có cột vendor, model, firmware_version cho BootNotification.

Các cột này được tạo trong 0003_create_charge_points nhưng migration này cung cấp
guard idempotent để môi trường nào thiếu cũng được bổ sung đúng kiểu.
Tham chiếu: 02_DAC_TA_DU_AN.md T-16, S-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261002_t16"
down_revision: str | None = "20260928_wallet"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("charge_points")}

    # Thêm cột vendor nếu chưa có — thiếu thì lưu NULL (T-16 NFR)
    if "vendor" not in existing:
        op.add_column(
            "charge_points",
            sa.Column("vendor", sa.String(255), nullable=True),
        )

    # Thêm cột model nếu chưa có
    if "model" not in existing:
        op.add_column(
            "charge_points",
            sa.Column("model", sa.String(255), nullable=True),
        )

    # Thêm cột firmware_version nếu chưa có
    if "firmware_version" not in existing:
        op.add_column(
            "charge_points",
            sa.Column("firmware_version", sa.String(100), nullable=True),
        )


def downgrade() -> None:
    # Lùi: xóa cột nếu migration này đã thêm chúng.
<<<<<<< HEAD
    # Guard tương tự để tránh lỗi trên DB chưa có cột.
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("charge_points")}

    if "firmware_version" in existing:
        op.drop_column("charge_points", "firmware_version")
    if "model" in existing:
        op.drop_column("charge_points", "model")
    if "vendor" in existing:
        op.drop_column("charge_points", "vendor")
=======
    # Nhưng vì các cột này đã được tạo từ 0003_create_charge_points,
    # chúng ta không nên drop chúng ở đây để tránh lỗi.
    pass
>>>>>>> 8cf926d056b9e2b97c0e961073b67f863da7c728
