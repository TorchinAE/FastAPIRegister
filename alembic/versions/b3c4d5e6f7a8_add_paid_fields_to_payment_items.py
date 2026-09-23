"""add paid_amount and paid_date to payment_items

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-08-19 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("payment_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("paid_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("paid_date", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("payment_items", schema=None) as batch_op:
        batch_op.drop_column("paid_date")
        batch_op.drop_column("paid_amount")
