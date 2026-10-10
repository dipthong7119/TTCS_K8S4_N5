"""Protect wallet ledger rows from updates and deletes."""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6a9fa9862b72"
down_revision: str | None = "h20261010_monthly_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_wallet_ledger_update
            BEFORE UPDATE ON wallet_ledger
            BEGIN
                SELECT RAISE(ABORT, 'wallet_ledger is append-only, UPDATE is not allowed');
            END;
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_wallet_ledger_delete
            BEFORE DELETE ON wallet_ledger
            BEGIN
                SELECT RAISE(ABORT, 'wallet_ledger is append-only, DELETE is not allowed');
            END;
            """
        )
    elif op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_wallet_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'wallet_ledger is append-only, UPDATE and DELETE are not allowed';
                RETURN OLD;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            "DROP TRIGGER IF EXISTS prevent_wallet_ledger_mutation ON wallet_ledger;"
        )
        op.execute(
            """
            CREATE TRIGGER prevent_wallet_ledger_mutation
            BEFORE UPDATE OR DELETE ON wallet_ledger
            FOR EACH ROW EXECUTE FUNCTION prevent_wallet_ledger_mutation();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS prevent_wallet_ledger_update;")
        op.execute("DROP TRIGGER IF EXISTS prevent_wallet_ledger_delete;")
    elif op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS prevent_wallet_ledger_mutation ON wallet_ledger;"
        )
        op.execute("DROP FUNCTION IF EXISTS prevent_wallet_ledger_mutation();")
