"""add_equipment_composition_and_calc_items

Revision ID: 35fd24924ec1
Revises: d991e1df2297
Create Date: 2026-08-26 19:28:26.933069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '35fd24924ec1'
down_revision: Union[str, Sequence[str], None] = 'd991e1df2297'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Add columns to equipment (raw SQL to avoid batch reflection issues)
    eq_cols = [c['name'] for c in inspector.get_columns('equipment')]
    if 'section_id' not in eq_cols:
        conn.execute(sa.text("ALTER TABLE equipment ADD COLUMN section_id INTEGER REFERENCES equipment_sections(id)"))
    if 'is_composite' not in eq_cols:
        conn.execute(sa.text("ALTER TABLE equipment ADD COLUMN is_composite BOOLEAN NOT NULL DEFAULT 0"))

    # Create equipment_composition
    tables = inspector.get_table_names()
    if 'equipment_composition' not in tables:
        conn.execute(sa.text("""
            CREATE TABLE equipment_composition (
                id INTEGER NOT NULL PRIMARY KEY,
                parent_id INTEGER NOT NULL REFERENCES equipment(id),
                child_id INTEGER NOT NULL REFERENCES equipment(id),
                quantity INTEGER NOT NULL DEFAULT 1,
                created_by VARCHAR(100),
                created_at DATETIME,
                updated_at DATETIME,
                changed_by_id INTEGER REFERENCES users(id)
            )
        """))

    # Create calc_items
    if 'calc_items' not in tables:
        conn.execute(sa.text("""
            CREATE TABLE calc_items (
                id INTEGER NOT NULL PRIMARY KEY,
                request_id INTEGER NOT NULL REFERENCES requests(id),
                calc_type VARCHAR(50) NOT NULL,
                equipment_id INTEGER NOT NULL REFERENCES equipment(id),
                quantity INTEGER NOT NULL DEFAULT 1,
                custom_name VARCHAR(200),
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_by VARCHAR(100),
                created_at DATETIME,
                updated_at DATETIME,
                changed_by_id INTEGER REFERENCES users(id)
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS calc_items"))
    conn.execute(sa.text("DROP TABLE IF EXISTS equipment_composition"))
    conn.execute(sa.text("ALTER TABLE equipment DROP COLUMN is_composite"))
    conn.execute(sa.text("ALTER TABLE equipment DROP COLUMN section_id"))
