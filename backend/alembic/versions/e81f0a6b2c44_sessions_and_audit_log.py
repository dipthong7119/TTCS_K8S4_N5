"""Add charging transactions and immutable audit history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e81f0a6b2c44"
down_revision: str | None = "d4e9f7210b8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "charging_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("charge_point_id", sa.Integer(), nullable=True),
        sa.Column("charge_point_code", sa.String(50), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=True),
        sa.Column("station_name", sa.String(255), nullable=False),
        sa.Column("connector_number", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("driver_name", sa.String(255), nullable=True),
        sa.Column("id_tag_id", sa.Integer(), nullable=True),
        sa.Column("id_tag", sa.String(50), nullable=True),
        sa.Column("meter_start_wh", sa.Integer(), nullable=False),
        sa.Column("meter_stop_wh", sa.Integer(), nullable=True),
        sa.Column("energy_kwh", sa.Numeric(12, 3), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("remote_stop_requested_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("stop_reason", sa.String(50), nullable=True),
        sa.Column("anomaly_reason", sa.String(50), nullable=True),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("demo_key", sa.String(80), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["charge_point_id"], ["charge_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["id_tag_id"], ["id_tags.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'anomaly', 'needs_review')",
            name="ck_charging_sessions_status",
        ),
    )
    op.create_index("ix_charging_sessions_user_started", "charging_sessions", ["user_id", "started_at"])
    op.create_index("ix_charging_sessions_cp_started", "charging_sessions", ["charge_point_code", "started_at"])
    op.create_index("ix_charging_sessions_status_started", "charging_sessions", ["status", "started_at"])
    op.create_index(
        "uq_active_session_per_connector",
        "charging_sessions",
        ["charge_point_id", "connector_number"],
        unique=True,
        sqlite_where=sa.text("ended_at IS NULL"),
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(80), nullable=True),
        sa.Column("charge_point_code", sa.String(50), nullable=True),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_created_id", "audit_logs", ["created_at", "id"])
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_logs_cp_created", "audit_logs", ["charge_point_code", "created_at"])

    op.create_table(
        "meter_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(), nullable=False),
        sa.Column("measurand", sa.String(80), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["charging_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_meter_values_session_measured", "meter_values", ["session_id", "measured_at"]
    )

    op.create_table(
        "orphan_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("charge_point_code", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("connector_number", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_orphan_messages_cp_received", "orphan_messages", ["charge_point_code", "received_at"]
    )
    op.create_index(
        "ix_orphan_messages_transaction", "orphan_messages", ["transaction_id", "received_at"]
    )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs "
            "BEGIN SELECT RAISE(ABORT, 'audit_logs are append-only'); END"
        )
        op.execute(
            "CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs "
            "BEGIN SELECT RAISE(ABORT, 'audit_logs are append-only'); END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION prevent_audit_log_mutation() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'audit_logs are append-only'; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER audit_logs_no_mutation BEFORE UPDATE OR DELETE ON audit_logs "
            "FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()"
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update")
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_no_mutation ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.drop_index("ix_orphan_messages_transaction", table_name="orphan_messages")
    op.drop_index("ix_orphan_messages_cp_received", table_name="orphan_messages")
    op.drop_table("orphan_messages")
    op.drop_index("ix_meter_values_session_measured", table_name="meter_values")
    op.drop_table("meter_values")
    op.drop_index("ix_audit_logs_cp_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("uq_active_session_per_connector", table_name="charging_sessions")
    op.drop_index("ix_charging_sessions_status_started", table_name="charging_sessions")
    op.drop_index("ix_charging_sessions_cp_started", table_name="charging_sessions")
    op.drop_index("ix_charging_sessions_user_started", table_name="charging_sessions")
    op.drop_table("charging_sessions")
