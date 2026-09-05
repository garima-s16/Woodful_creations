"""Add the Category -> Subcategory -> Material hierarchy and a dynamic
attribute system (material_categories, material_subcategories,
material_attribute_definitions, material_attribute_values), plus a
nullable subcategory_id link on the existing materials table.

Existing Material rows are NOT restructured or renamed - every current
consumer (dashboard, chatbot, PDF/Excel exports, purchases, issues)
keeps reading the same materials table and the same category string
column unchanged. This migration only adds the new hierarchy above it
and links each existing material to a real subcategory, so both the
old flat category string and the new structured hierarchy are valid
and in sync going forward.

Data migration: creates one neutral parent category ("General
Materials") and one subcategory per distinct existing category string
value already in use, then links each material row to its matching new
subcategory. This is a deliberately conservative default - it doesn't
invent a taxonomy (e.g. guessing "Board & Wood Materials" as a parent
for "HDHMR") since that's a real business decision the user should
make, not one to fabricate during a migration. Materials with no
category set are left unlinked (subcategory_id stays NULL) rather than
guessed at.

subcategory_id has an inline foreign key, so - same reasoning as prior
migrations that added a column with an inline FK - this needs SQLite
batch mode with a naming convention (covering the materials table's
existing unnamed constraints too, not just the new one).

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
from app.platform.database.migration_guards import create_table_if_missing, create_index_if_missing, column_exists

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

DEFAULT_CATEGORY_NAME = "General Materials"


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # An earlier version of this app created a much simpler
    # `material_categories` table directly via SQLAlchemy's create_all()
    # (flat name/description columns, no business_id) before this
    # Category -> Subcategory hierarchy - and this migration - existed.
    # Left alone, that stray table makes create_table below fail with
    # "table already exists". It's safe to replace automatically only
    # if it's still empty; if it somehow already has data, stop and ask
    # for a manual look rather than silently discarding it. If it
    # already has the CURRENT (business_id) shape, leave it alone
    # entirely - it's the real, already-migrated table, not the stray
    # legacy one.
    if insp.has_table("material_categories"):
        existing_columns = {c["name"] for c in insp.get_columns("material_categories")}
        is_legacy_shape = "business_id" not in existing_columns
        if is_legacy_shape:
            row_count = conn.execute(sa.text("SELECT COUNT(*) FROM material_categories")).scalar()
            if row_count:
                raise RuntimeError(
                    "A pre-existing 'material_categories' table with data was found "
                    "that predates this migration's schema (missing business_id). "
                    "Migrate that data manually, then re-run this migration."
                )
            op.drop_table("material_categories")

    create_table_if_missing(
        conn, "material_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_material_categories_business_id"),
        sa.UniqueConstraint("name", name="uq_material_categories_name"),
    )
    create_index_if_missing(conn, "ix_material_categories_name", "material_categories", ["name"])

    create_table_if_missing(
        conn, "material_subcategories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("material_categories.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("business_id", name="uq_material_subcategories_business_id"),
        sa.UniqueConstraint("category_id", "name", name="uq_subcategory_per_category"),
    )
    create_index_if_missing(conn, "ix_material_subcategories_name", "material_subcategories", ["name"])
    create_index_if_missing(conn, "ix_material_subcategories_category_id", "material_subcategories", ["category_id"])

    create_table_if_missing(
        conn, "material_attribute_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("material_subcategories.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("unit_label", sa.String(20), nullable=True),
        sa.Column("select_options", sa.String(500), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("subcategory_id", "name", name="uq_attribute_per_subcategory"),
    )
    create_index_if_missing(conn, "ix_material_attribute_definitions_subcategory_id",
                             "material_attribute_definitions", ["subcategory_id"])

    create_table_if_missing(
        conn, "material_attribute_values",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("attribute_definition_id", sa.Integer(),
                  sa.ForeignKey("material_attribute_definitions.id"), nullable=False),
        sa.Column("value_text", sa.String(255), nullable=True),
        sa.Column("value_number", sa.Numeric(14, 4), nullable=True),
        sa.UniqueConstraint("material_id", "attribute_definition_id", name="uq_value_per_material_attribute"),
    )
    create_index_if_missing(conn, "ix_material_attribute_values_material_id", "material_attribute_values", ["material_id"])
    create_index_if_missing(conn, "ix_material_attribute_values_attribute_definition_id",
                             "material_attribute_values", ["attribute_definition_id"])
    create_index_if_missing(conn, "ix_material_attribute_values_value_number", "material_attribute_values", ["value_number"])

    subcategory_column_existed_already = column_exists(conn, "materials", "subcategory_id")
    if not subcategory_column_existed_already:
        with op.batch_alter_table("materials", naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column(
                "subcategory_id", sa.Integer(),
                sa.ForeignKey("material_subcategories.id", name="fk_materials_subcategory_id_material_subcategories"),
                nullable=True,
            ))
            batch_op.create_index("ix_materials_subcategory_id", ["subcategory_id"])

    # --- Data migration: link existing materials to real subcategories ---
    # Only runs once - if the column already existed AND already has at
    # least one material linked, this has already been done; running it
    # again would create a second "General Materials" parent and
    # duplicate subcategories rather than being a genuine no-op.
    already_linked = False
    if subcategory_column_existed_already:
        already_linked = conn.execute(
            sa.text("SELECT COUNT(*) FROM materials WHERE subcategory_id IS NOT NULL")
        ).scalar() > 0

    if not already_linked:
        materials_table = sa.table(
            "materials", sa.column("id", sa.Integer), sa.column("category", sa.String),
            sa.column("subcategory_id", sa.Integer),
        )
        categories_table = sa.table(
            "material_categories", sa.column("id", sa.Integer), sa.column("name", sa.String),
            sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        )
        subcategories_table = sa.table(
            "material_subcategories", sa.column("id", sa.Integer), sa.column("category_id", sa.Integer),
            sa.column("name", sa.String), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
        )

        distinct_categories = conn.execute(
            sa.select(materials_table.c.category).distinct().where(materials_table.c.category.isnot(None))
        ).fetchall()

        if distinct_categories:
            now = datetime.utcnow()
            result = conn.execute(
                categories_table.insert().values(name=DEFAULT_CATEGORY_NAME, created_at=now, updated_at=now)
            )
            parent_category_id = result.inserted_primary_key[0]

            for (category_name,) in distinct_categories:
                if not category_name or not category_name.strip():
                    continue
                sub_result = conn.execute(
                    subcategories_table.insert().values(
                        category_id=parent_category_id, name=category_name.strip(), created_at=now, updated_at=now,
                    )
                )
                subcategory_id = sub_result.inserted_primary_key[0]
                conn.execute(
                    materials_table.update()
                    .where(materials_table.c.category == category_name)
                    .values(subcategory_id=subcategory_id)
                )


def downgrade() -> None:
    with op.batch_alter_table("materials", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_materials_subcategory_id")
        batch_op.drop_column("subcategory_id")
    op.drop_table("material_attribute_values")
    op.drop_table("material_attribute_definitions")
    op.drop_table("material_subcategories")
    op.drop_table("material_categories")
