"""add profitability org calc costs delivery

Revision ID: 1ed19bd75ce0
Revises: aab557719d57
Create Date: 2026-09-30 22:25:55.085361

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ed19bd75ce0"
down_revision: str | Sequence[str] | None = "aab557719d57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # deliveries table
    op.create_table(
        "deliveries",
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("cost_per_truck", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("trucks_count", sa.Integer(), nullable=False),
        sa.Column("final_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # organizations: add profitability
    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("profitability", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False)
        )

    # requests: add calc cost columns
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tkp_calc_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("corpusa_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("kso_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("kru_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("sho_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("ktp_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("pku_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("pus_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("delivery_cost", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.drop_column("delivery_cost")
        batch_op.drop_column("pus_cost")
        batch_op.drop_column("pku_cost")
        batch_op.drop_column("ktp_cost")
        batch_op.drop_column("sho_cost")
        batch_op.drop_column("kru_cost")
        batch_op.drop_column("kso_cost")
        batch_op.drop_column("corpusa_cost")
        batch_op.drop_column("tkp_calc_cost")

    with op.batch_alter_table("organizations", schema=None) as batch_op:
        batch_op.drop_column("profitability")

    op.drop_table("deliveries")
