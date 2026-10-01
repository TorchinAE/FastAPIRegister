"""add voltage field to materials

Revision ID: c1d2e3f4a5b6
Revises: be6ef4b05c1a
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'be6ef4b05c1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("materials")}
    if "voltage" not in columns:
        with op.batch_alter_table("materials", schema=None) as batch_op:
            batch_op.add_column(sa.Column("voltage", sa.String(50), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("materials")}
    if "voltage" in columns:
        with op.batch_alter_table("materials", schema=None) as batch_op:
            batch_op.drop_column("voltage")