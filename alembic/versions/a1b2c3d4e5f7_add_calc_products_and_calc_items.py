"""add_calc_products_and_calc_items

Revision ID: a1b2c3d4e5f7
Revises: d991e1df2297
Create Date: 2026-08-26 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'd991e1df2297'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'calc_products' not in tables:
        conn.execute(sa.text("""
            CREATE TABLE calc_products (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                section_id INTEGER REFERENCES equipment_sections(id),
                created_by VARCHAR(100),
                created_at DATETIME,
                updated_at DATETIME,
                changed_by_id INTEGER REFERENCES users(id)
            )
        """))

    if 'calc_product_components' not in tables:
        conn.execute(sa.text("""
            CREATE TABLE calc_product_components (
                id INTEGER NOT NULL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES calc_products(id),
                equipment_id INTEGER NOT NULL REFERENCES equipment(id),
                quantity INTEGER NOT NULL DEFAULT 1,
                created_by VARCHAR(100),
                created_at DATETIME,
                updated_at DATETIME,
                changed_by_id INTEGER REFERENCES users(id)
            )
        """))

    if 'calc_items' not in tables:
        conn.execute(sa.text("""
            CREATE TABLE calc_items (
                id INTEGER NOT NULL PRIMARY KEY,
                request_id INTEGER NOT NULL REFERENCES requests(id),
                calc_type VARCHAR(50) NOT NULL,
                product_id INTEGER NOT NULL REFERENCES calc_products(id),
                quantity INTEGER NOT NULL DEFAULT 1,
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
    conn.execute(sa.text("DROP TABLE IF EXISTS calc_product_components"))
    conn.execute(sa.text("DROP TABLE IF EXISTS calc_products"))
