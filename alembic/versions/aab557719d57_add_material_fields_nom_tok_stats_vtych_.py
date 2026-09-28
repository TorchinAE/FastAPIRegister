"""add material fields nom_tok stats vtych vykat ruchn el_priv

Revision ID: aab557719d57
Revises: 5ae59e2b2636
Create Date: 2026-09-28 13:08:03.177682

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aab557719d57"
down_revision: str | Sequence[str] | None = "5ae59e2b2636"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("materials", schema=None) as batch_op:
        batch_op.add_column(sa.Column("nom_tok", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("stats", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("vtych", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("vykat", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("ruchn", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("el_priv", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("materials", schema=None) as batch_op:
        batch_op.drop_column("el_priv")
        batch_op.drop_column("ruchn")
        batch_op.drop_column("vykat")
        batch_op.drop_column("vtych")
        batch_op.drop_column("stats")
        batch_op.drop_column("nom_tok")
