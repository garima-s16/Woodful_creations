"""Add the flexible Location tree (Section 8: Warehouse -> Area -> Rack
-> Bin, or as many/few levels as the business actually uses) and a
nullable location_id link on Material.

The locations table is a fresh CREATE TABLE - its self-referential
parent_id FK is natively supported by SQLite in a CREATE TABLE (the
limitation that requires batch mode is specifically about ALTER TABLE
ADD COLUMN with an inline FK, not table creation).

Material.location_id, however, IS an ALTER TABLE ADD COLUMN with an
inline FK, so - same reasoning as every prior migration that added a
column with an inline FK - this needs SQLite batch mode with a naming
convention.

Existing Material.location (a plain string) is untouched - every
current consumer keeps reading it directly. No data migration is
attempted here: unlike the category migration, an existing free-text
location string like "Rack A1" cannot be safely parsed into a real
tree structure without guessing an intended hierarchy the business
never actually specified - that would be inventing structure, not
preserving data, so existing materials are left with location_id=NULL
and their original location string intact.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("location_type", sa.String(50), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_locations_business_id"),
        sa.UniqueConstraint("parent_id", "name", name="uq_location_name_per_parent"),
    )
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_parent_id", "locations", ["parent_id"])

    with op.batch_alter_table("materials", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column(
            "location_id", sa.Integer(),
            sa.ForeignKey("locations.id", name="fk_materials_location_id_locations"), nullable=True,
        ))
        batch_op.create_index("ix_materials_location_id", ["location_id"])


def downgrade() -> None:
    with op.batch_alter_table("materials", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_materials_location_id")
        batch_op.drop_column("location_id")
    op.drop_table("locations")
