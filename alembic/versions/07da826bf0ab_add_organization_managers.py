"""add_organization_managers

Revision ID: 07da826bf0ab
Revises: 6b915867262d
Create Date: 2026-08-12 23:52:16.636786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '07da826bf0ab'
down_revision: Union[str, Sequence[str], None] = '6b915867262d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create junction table
    op.create_table('organization_managers',
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('manager_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['manager_id'], ['managers.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('organization_id', 'manager_id')
    )
    # Migrate existing data
    op.execute(
        "INSERT INTO organization_managers (organization_id, manager_id) "
        "SELECT id, manager_id FROM organizations WHERE manager_id IS NOT NULL"
    )
    # Recreate organizations table without manager_id
    op.execute("ALTER TABLE organizations RENAME TO organizations_old")
    op.execute("""
        CREATE TABLE organizations (
            name VARCHAR(100) NOT NULL,
            inn VARCHAR(12),
            address VARCHAR(200),
            server_address_slug VARCHAR(200) NOT NULL,
            director_id INTEGER NOT NULL,
            id INTEGER NOT NULL,
            created_by VARCHAR(100),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            changed_by_id INTEGER,
            PRIMARY KEY (id),
            FOREIGN KEY(changed_by_id) REFERENCES managers (id),
            FOREIGN KEY(director_id) REFERENCES directors (id),
            UNIQUE (inn),
            UNIQUE (name)
        )
    """)
    op.execute("""
        INSERT INTO organizations (name, inn, address, server_address_slug, director_id, id, created_by, created_at, updated_at, changed_by_id)
        SELECT name, inn, address, server_address_slug, director_id, id, created_by, created_at, updated_at, changed_by_id
        FROM organizations_old
    """)
    op.execute("DROP TABLE organizations_old")


def downgrade() -> None:
    # Add manager_id back
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('manager_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key('fk_org_manager', 'managers', ['manager_id'], ['id'])
    # Restore data
    op.execute(
        "UPDATE organizations SET manager_id = ("
        "SELECT manager_id FROM organization_managers "
        "WHERE organization_managers.organization_id = organizations.id LIMIT 1"
        ") WHERE id IN (SELECT organization_id FROM organization_managers)"
    )
    op.drop_table('organization_managers')
