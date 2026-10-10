"""manual_topup_trigger

Revision ID: 6a9fa9862b72
Revises: e97a880b36e9
Create Date: 2026-10-10 15:01:38.046716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a9fa9862b72'
down_revision: Union[str, None] = 'e97a880b36e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Trigger SQLite chặn UPDATE và DELETE trên wallet_ledger
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS prevent_wallet_ledger_update
    BEFORE UPDATE ON wallet_ledger
    BEGIN
        SELECT RAISE(ABORT, 'wallet_ledger is append-only, UPDATE is not allowed');
    END;
    """)
    
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS prevent_wallet_ledger_delete
    BEFORE DELETE ON wallet_ledger
    BEGIN
        SELECT RAISE(ABORT, 'wallet_ledger is append-only, DELETE is not allowed');
    END;
    """)

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_wallet_ledger_update;")
    op.execute("DROP TRIGGER IF EXISTS prevent_wallet_ledger_delete;")
