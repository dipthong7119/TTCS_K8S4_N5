"""add needs_review to charging_sessions

Revision ID: h20261007_needs_review
Revises: h20261006_meter_values
Create Date: 2026-10-07 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h20261007_needs_review'
down_revision: Union[str, None] = 'h20261006_meter_values'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('charging_sessions') as batch_op:
        batch_op.add_column(sa.Column('needs_review', sa.Boolean(), server_default=sa.text('0'), nullable=False))
        batch_op.add_column(sa.Column('review_reason', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('charging_sessions') as batch_op:
        batch_op.drop_column('review_reason')
        batch_op.drop_column('needs_review')
