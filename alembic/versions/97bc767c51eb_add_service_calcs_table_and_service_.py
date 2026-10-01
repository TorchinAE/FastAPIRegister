"""add service_calcs table and service cost fields to requests

Revision ID: 97bc767c51eb
Revises: 1ed19bd75ce0
Create Date: 2026-10-01 07:31:09.540975

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "97bc767c51eb"
down_revision: Union[str, Sequence[str], None] = "1ed19bd75ce0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # create_table idempotent: create_all may have already created it
    has_table = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='service_calcs'")
    ).fetchone()
    if not has_table:
        op.create_table(
            "service_calcs",
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("section", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("base_cost", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("profitability_percent", sa.Numeric(precision=5, scale=2), nullable=False),
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

    # Add columns idempotently (create_all may have already created them)
    existing_cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(requests)"))}
    with op.batch_alter_table("requests", schema=None) as batch_op:
        if "chief_engineer_cost" not in existing_cols:
            batch_op.add_column(sa.Column("chief_engineer_cost", sa.Numeric(precision=12, scale=2), nullable=False))
        if "smr_cost" not in existing_cols:
            batch_op.add_column(sa.Column("smr_cost", sa.Numeric(precision=12, scale=2), nullable=False))
        if "pnr_cost" not in existing_cols:
            batch_op.add_column(sa.Column("pnr_cost", sa.Numeric(precision=12, scale=2), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.drop_column("pnr_cost")
        batch_op.drop_column("smr_cost")
        batch_op.drop_column("chief_engineer_cost")

    op.drop_table("service_calcs")