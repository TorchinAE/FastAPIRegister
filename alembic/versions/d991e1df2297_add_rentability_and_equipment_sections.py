"""add_rentability_and_equipment_sections

Revision ID: d991e1df2297
Revises: c4d5e6f7a8b9
Create Date: 2026-08-26 18:37:34.518201

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd991e1df2297'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add rentability to organizations (if not already added)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    org_cols = [c['name'] for c in inspector.get_columns('organizations')]
    if 'rentability' not in org_cols:
        with op.batch_alter_table('organizations', schema=None) as batch_op:
            batch_op.add_column(sa.Column('rentability', sa.Numeric(precision=5, scale=2), nullable=True))

    # Create equipment_sections table (if not exists)
    tables = inspector.get_table_names()
    if 'equipment_sections' not in tables:
        op.create_table(
            'equipment_sections',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(100), unique=True, nullable=False),
            sa.Column('created_by', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('changed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        )

    # Seed default equipment sections
    sections = ["ВА", "Schnaider", "IEK", "EKF", "CHINT", "ESQ", "ТТ04", "ТТ62"]
    for name in sections:
        existing = conn.execute(sa.text(f"SELECT id FROM equipment_sections WHERE name = '{name}'")).fetchone()
        if not existing:
            conn.execute(sa.text(f"INSERT INTO equipment_sections (name) VALUES ('{name}')"))


def downgrade() -> None:
    op.drop_table('equipment_sections')
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('rentability')
