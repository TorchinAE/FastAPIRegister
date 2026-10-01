"""add date field to materials

Revision ID: be6ef4b05c1a
Revises: 97bc767c51eb
Create Date: 2026-10-01 08:48:33.451459

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be6ef4b05c1a'
down_revision: Union[str, Sequence[str], None] = '97bc767c51eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("materials")}
    if "date" not in columns:
        with op.batch_alter_table("materials", schema=None) as batch_op:
            batch_op.add_column(sa.Column("date", sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("materials")}
    if "date" in columns:
        with op.batch_alter_table("materials", schema=None) as batch_op:
            batch_op.drop_column("date")