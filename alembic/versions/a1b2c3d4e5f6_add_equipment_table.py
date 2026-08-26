"""add equipment table and update requests

Revision ID: a1b2c3d4e5f6
Revises: 07da826bf0ab
Create Date: 2026-08-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '07da826bf0ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create equipment table
    op.create_table('equipment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by_id'], ['managers.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Add new columns to requests
    with op.batch_alter_table('requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('equipment_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cost', sa.Numeric(12, 2), server_default='0'))
        batch_op.create_foreign_key('fk_requests_equipment', 'equipment', ['equipment_id'], ['id'])

    # Remove old equipment columns from requests
    old_columns = ['bktpb', 'ktpb', 'ktp', 'kso_393', 'kso_204', 'k_104', 'k_104m', 'sho', 'pku', 'pus', 'parn']
    with op.batch_alter_table('requests', schema=None) as batch_op:
        for col in old_columns:
            batch_op.drop_column(col)


def downgrade() -> None:
    # Add old equipment columns back
    old_columns = [
        ('bktpb', sa.Integer(), '0'),
        ('ktpb', sa.Integer(), '0'),
        ('ktp', sa.Integer(), '0'),
        ('kso_393', sa.Integer(), '0'),
        ('kso_204', sa.Integer(), '0'),
        ('k_104', sa.Integer(), '0'),
        ('k_104m', sa.Integer(), '0'),
        ('sho', sa.Integer(), '0'),
        ('pku', sa.Integer(), '0'),
        ('pus', sa.Integer(), '0'),
        ('parn', sa.Integer(), '0'),
    ]
    with op.batch_alter_table('requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_requests_equipment', type_='foreignkey')
        batch_op.drop_column('cost')
        batch_op.drop_column('equipment_id')
        for col_name, col_type, default in old_columns:
            batch_op.add_column(sa.Column(col_name, col_type, server_default=default))

    op.drop_table('equipment')
