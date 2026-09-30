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


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    return conn.dialect.has_table(conn, name)


def _column_exists(table: str, column: str) -> bool:
    rows = op.get_bind().execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    # deliveries table
    if not _table_exists("deliveries"):
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
    if not _column_exists("organizations", "profitability"):
        with op.batch_alter_table("organizations", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("profitability", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False)
            )

    # requests: add calc cost columns
    cost_columns = [
        "tkp_calc_cost",
        "corpusa_cost",
        "kso_cost",
        "kru_cost",
        "sho_cost",
        "ktp_cost",
        "pku_cost",
        "pus_cost",
        "delivery_cost",
    ]
    missing = [c for c in cost_columns if not _column_exists("requests", c)]
    if missing:
        with op.batch_alter_table("requests", schema=None) as batch_op:
            for col_name in missing:
                batch_op.add_column(
                    sa.Column(col_name, sa.Numeric(precision=12, scale=2), server_default="0", nullable=False)
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