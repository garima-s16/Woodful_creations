"""Baseline - consolidated current Woodful schema.

Offline consolidation of the historical 0001-0072 migration chain plus
0073's own change into a single baseline, per explicit instruction to
proceed without live Neon connectivity. Uses revision "0073" (not a
new ID) so a database already at 0073 requires no upgrade/stamp to
align with this file - see section on Neon compatibility below.

METHODOLOGY (fully documented since it could not be validated against
a live or local PostgreSQL database - no such environment was
available in this sandbox):

1. Column existence, types, nullability, and foreign keys were
   extracted via Python's ast module reading every current
   app/modules/*/models.py file directly (not executed - SQLAlchemy
   itself is not installed in this environment either). Verified
   against 632 columns across 72 tables with zero parse failures, and
   spot-checked several tables (users, orders, estimates) by hand
   against the literal model source.

2. server_default values are NOT reliably present in the current
   models (this codebase deliberately keeps Python-side `default=`
   separate from database-level `server_default=`, and only
   migrations declare the latter) - so these were tracked separately
   by parsing all 72 migration files IN ORDER and following each
   (table, column)'s server_default through create_table_if_missing/
   add_column_if_missing/op.add_column/op.alter_column/batch_op calls,
   taking the most recent value for each column as authoritative (a
   later migration can change or clear an earlier one). 112 (table,
   column) pairs were found this way.

3. Two schema elements exist ONLY in migration history, not
   expressible as a plain SQLAlchemy Column() and therefore invisible
   to step 1 - found and manually verified by reading every migration
   that mixes schema DDL with data operations:
   - estimates.order_id: the model itself only declares a plain,
     non-unique index (index=True) - but migration 0067 explicitly
     adds a UNIQUE index (enforcing "one estimate per order" at the
     database level) that is never later dropped. The migration's
     unique constraint is used here, not the model's weaker one.
   - payments.reference_number: migration 0062 adds a PostgreSQL/
     SQLite partial/filtered unique index (only cash-generated
     references matching 'CASH-%' must be unique) - reproduced here
     as schema DDL. That migration's one-time de-duplication of
     pre-existing duplicate references is a historical data fixup and
     is deliberately NOT replayed here, per instruction.

4. Table creation order is topologically sorted by foreign-key
   dependency (computed from the same extracted column data) - no
   dependency cycles were found across all 72 tables.

KNOWN LIMITATIONS - genuinely could not be verified without a live or
local PostgreSQL instance, neither of which was available:
- Whether every migration's server_default was captured correctly by
  the AST walk (the walk explicitly handles create_table_if_missing,
  add_column_if_missing, op.add_column/create_table, and
  op.alter_column/batch_op.alter_column - the specific helper
  functions and call shapes actually used throughout this migration
  history, confirmed by grep against all 72 files - but a shape not
  covered by that list would silently be missed).
- Whether any check constraints, database views, functions, or
  triggers exist that were never introduced via a Python-visible
  Alembic operation at all (e.g. applied by hand directly against
  Neon outside of any migration) - a static read of this repository's
  migration history cannot detect anything that was never recorded in
  it in the first place.
- No autogenerate comparison against a live database was possible
  (Section 8 of the original spec) - this baseline has NOT been
  diffed against actual application metadata via Alembic tooling,
  since SQLAlchemy/Alembic are not installed in this environment.

Revision ID: 0073
Revises:
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database import create_table_if_missing, create_index_if_missing

revision = "0073"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_table_if_missing(bind, 
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False, server_default='standard'),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("specifications", sa.Text(), nullable=True),
        sa.Column("length", sa.Numeric(10, 2), nullable=True),
        sa.Column("width", sa.Numeric(10, 2), nullable=True),
        sa.Column("height", sa.Numeric(10, 2), nullable=True),
        sa.Column("dimension_unit", sa.String(10), nullable=True, server_default='in'),
        sa.Column("primary_material", sa.String(150), nullable=True),
        sa.Column("finish", sa.String(150), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default='Nos'),
        sa.Column("gst_percent", sa.Numeric(5, 2), nullable=True, server_default='18'),
        sa.Column("material_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("hardware_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("labour_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("machine_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("finish_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("packing_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("transport_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("other_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("overhead_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("cost_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    create_table_if_missing(bind, 
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("location_type", sa.String(50), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.UniqueConstraint("parent_id", "name", name="uq_location_name_per_parent"),
    )
    create_table_if_missing(bind, 
        "material_categories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "material_subcategories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("material_categories.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("category_id", "name", name="uq_subcategory_per_category"),
    )
    create_table_if_missing(bind, 
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("supplier_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("contact_person", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("gstin", sa.String(20), nullable=True),
        sa.Column("payment_terms", sa.String(50), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("material_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("material_subcategories.id"), nullable=True),
        sa.Column("brand_grade", sa.String(100), nullable=True),
        sa.Column("thickness_size", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("opening_stock", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("total_purchased", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("total_issued", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("current_stock", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("minimum_stock", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("average_rate", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("opening_stock_location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    create_table_if_missing(bind, 
        "product_materials",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity_required", sa.Numeric(10, 2), nullable=False, server_default='1'),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.UniqueConstraint("product_id", "material_id", name="uq_product_material_pair"),
    )
    create_table_if_missing(bind, 
        "rate_cards",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("rate_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=False, unique=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("specification", sa.String(255), nullable=True),
        sa.Column("location", sa.String(100), nullable=False, server_default='Indore, Madhya Pradesh'),
        sa.Column("uom", sa.String(20), nullable=False),
        sa.Column("market_reference_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("woodful_cost_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("woodful_selling_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("overhead_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("target_margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("wastage_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=True, server_default='18'),
        sa.Column("effective_from", sa.DateTime(), nullable=False),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=False, server_default='NOT_VERIFIED'),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("rate_cards.id"), nullable=True),
        sa.Column("override_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("override_by", sa.String(255), nullable=True),
        sa.Column("override_at", sa.DateTime(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_type", sa.String(20), nullable=False, server_default='Individual'),
        sa.Column("contact_person", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("alternate_phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("site_address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("pincode", sa.String(10), nullable=True),
        sa.Column("gstin", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Active'),
        sa.Column("lead_source", sa.String(100), nullable=True),
        sa.Column("first_contact_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("project_type", sa.String(100), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=False),
        sa.Column("delivery_date", sa.DateTime(), nullable=True),
        sa.Column("order_value", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default='18'),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("advance", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("other_received", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("total_received", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("project_status", sa.String(50), nullable=False, server_default='Enquiry'),
        sa.Column("design_status", sa.String(50), nullable=False, server_default='Pending'),
        sa.Column("execution_status", sa.String(50), nullable=False, server_default='Pending'),
        sa.Column("delivery_status", sa.String(50), nullable=False, server_default='Pending'),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("supervisor", sa.String(255), nullable=True),
        sa.Column("site_address", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "ai_workspace_reports",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "report_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("report_date", sa.DateTime(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("storage_identity", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("employee_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("designation", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("manager", sa.String(255), nullable=True),
        sa.Column("joining_date", sa.DateTime(), nullable=True),
        sa.Column("monthly_salary", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("status", sa.String(20), nullable=False, server_default='Active'),
        sa.Column("emergency_contact", sa.String(20), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("pan", sa.String(10), nullable=True),
        sa.Column("uan", sa.String(20), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bank_account_number", sa.String(30), nullable=True),
        sa.Column("tax_regime", sa.String(10), nullable=True),
    )
    create_table_if_missing(bind, 
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default='user'),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("profile_picture", sa.String(500), nullable=True),
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("otp_secret", sa.String(255), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("cannot_be_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
    )
    create_table_if_missing(bind, 
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("notification_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default='INFO'),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("related_entity_type", sa.String(30), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("action_path", sa.String(255), nullable=True),
        sa.Column("dedup_key", sa.String(150), nullable=True),
    )
    create_table_if_missing(bind, 
        "automation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("rule_key", sa.String(50), nullable=False),
        sa.Column("trigger_event", sa.String(50), nullable=False),
        sa.Column("condition_summary", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("related_entity_type", sa.String(30), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id"), nullable=True),
        sa.Column("dedup_key", sa.String(150), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "chat_learning_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("normalized_phrase", sa.String(500), nullable=False),
        sa.Column("resolved_tool", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default='pending'),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default='1'),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "estimates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("estimate_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("material_cost", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("labor_cost", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default='18'),
        sa.Column("margin_percent_override", sa.Numeric(5, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("status", sa.String(20), nullable=False, server_default='draft'),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default='1'),
        sa.Column("parent_estimate_id", sa.Integer(), sa.ForeignKey("estimates.id"), nullable=True),
    )
    create_table_if_missing(bind, 
        "estimate_line_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("estimate_id", sa.Integer(), sa.ForeignKey("estimates.id"), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default='1'),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("is_custom_item", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pricing_rule_applied", sa.String(40), nullable=True),
        sa.Column("applied_margin_percent", sa.Numeric(5, 2), nullable=True),
    )
    create_table_if_missing(bind, 
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default='1'),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("source_estimate_item_id", sa.Integer(), sa.ForeignKey("estimate_line_items.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("is_custom_item", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pricing_rule_applied", sa.String(40), nullable=True),
        sa.Column("applied_margin_percent", sa.Numeric(5, 2), nullable=True),
    )
    create_table_if_missing(bind, 
        "order_comments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
    )
    create_table_if_missing(bind, 
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("receipt_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("payment_type", sa.String(50), nullable=False),
        sa.Column("payment_mode", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("received_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "payment_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("storage_backend", sa.String(20), nullable=False),
        sa.Column("drive_file_id", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default='0'),
    )
    create_table_if_missing(bind, 
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("in_time", sa.DateTime(), nullable=True),
        sa.Column("out_time", sa.DateTime(), nullable=True),
        sa.Column("standard_hours", sa.Numeric(5, 2), nullable=False, server_default='8'),
        sa.Column("attendance_status", sa.String(20), nullable=False, server_default='Present'),
        sa.Column("overtime_hours", sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "leaves",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("leave_type", sa.String(20), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("days", sa.Numeric(4, 1), nullable=False, server_default='1'),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Pending'),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "salary_slips",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("month", sa.String(20), nullable=False),
        sa.Column("year", sa.String(4), nullable=False),
        sa.Column("working_days", sa.Numeric(5, 2), nullable=False, server_default='26'),
        sa.Column("paid_days", sa.Numeric(5, 2), nullable=False, server_default='26'),
        sa.Column("basic", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("da", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("hra", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("overtime_amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("pf_deduction", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("tds_deduction", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("other_deductions", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("advance_deduction", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("net_salary", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("status", sa.String(20), nullable=False, server_default='draft'),
    )
    create_table_if_missing(bind, 
        "working_calendar_weekdays",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("weekday", sa.String(10), nullable=False, unique=True),
        sa.Column("is_working", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    create_table_if_missing(bind, 
        "company_holidays",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_working", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "salary_advances",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("requested_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("request_date", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Pending'),
        sa.Column("approved_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approval_date", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("recovery_month", sa.String(20), nullable=True),
        sa.Column("recovery_year", sa.String(4), nullable=True),
        sa.Column("recovered_amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "supplier_materials",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("supplier_sku", sa.String(100), nullable=True),
        sa.Column("supplier_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_purchase_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("moq", sa.Integer(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("supplier_id", "material_id", name="uq_supplier_material_pair"),
    )
    create_table_if_missing(bind, 
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("purchase_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("expected_delivery_date", sa.DateTime(), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("gst_percent", sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column("gst_amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("invoice_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default='Paid'),
        sa.Column("receipt_status", sa.String(20), nullable=False, server_default='Received'),
        sa.Column("quantity_received", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    create_table_if_missing(bind, 
        "procurement_requirements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("required_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("available_quantity_at_creation", sa.Numeric(12, 2), nullable=False),
        sa.Column("shortage_quantity_at_creation", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default='Open'),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("required_by_date", sa.DateTime(), nullable=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id"), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "supplier_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("procurement_requirements.id"), nullable=False, unique=True),
        sa.Column("recommended_supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("recommended_reason", sa.String(255), nullable=True),
        sa.Column("selected_supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("decision_reason", sa.String(255), nullable=True),
        sa.Column("decided_by", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "personal_cart_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("material_name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default='1'),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("supplier_name", sa.String(255), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='ACTIVE'),
    )
    create_table_if_missing(bind, 
        "material_attribute_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("material_subcategories.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False, server_default='text'),
        sa.Column("unit_label", sa.String(20), nullable=True),
        sa.Column("select_options", sa.String(500), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint("subcategory_id", "name", name="uq_attribute_per_subcategory"),
    )
    create_table_if_missing(bind, 
        "material_attribute_values",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("attribute_definition_id", sa.Integer(), sa.ForeignKey("material_attribute_definitions.id"), nullable=False),
        sa.Column("value_text", sa.String(255), nullable=True),
        sa.Column("value_number", sa.Numeric(14, 4), nullable=True),
        sa.UniqueConstraint("material_id", "attribute_definition_id", name="uq_value_per_material_attribute"),
    )
    create_table_if_missing(bind, 
        "stock_transfers",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("from_location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("to_location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("transferred_by", sa.String(100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("issue_code", sa.String(20), nullable=False, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity_issued", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("issued_to", sa.String(255), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("purpose", sa.String(255), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("rate_at_issue", sa.Numeric(12, 2), nullable=True),
    )
    create_table_if_missing(bind, 
        "stock_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("adjustment_type", sa.String(30), nullable=False),
        sa.Column("related_issue_id", sa.Integer(), sa.ForeignKey("issues.id"), nullable=True),
        sa.Column("quantity_delta", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock_before", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("adjusted_by", sa.String(100), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
    )
    create_table_if_missing(bind, 
        "stock_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_type", sa.String(20), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "daily_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("task_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id"), nullable=True),
        sa.Column("task_description", sa.String(500), nullable=False),
        sa.Column("task_category", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("planned_start", sa.Time(), nullable=True),
        sa.Column("planned_end", sa.Time(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Not Started'),
        sa.Column("completion_percent", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("actual_completed_at", sa.DateTime(), nullable=True),
        sa.Column("checked_by", sa.String(255), nullable=True),
        sa.Column("delay_reason", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), sa.ForeignKey("daily_tasks.id"), nullable=True),
        sa.Column("previous_task_id", sa.Integer(), sa.ForeignKey("daily_tasks.id"), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("due_date_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    create_table_if_missing(bind, 
        "task_comments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("daily_tasks.id"), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
    )
    create_table_if_missing(bind, 
        "work_centres",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("capacity_hours_per_day", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "production_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("job_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("machine", sa.String(100), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("operation", sa.String(255), nullable=True),
        sa.Column("stage", sa.String(50), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
        sa.Column("planned_qty", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("completed_qty", sa.Integer(), nullable=False, server_default='0'),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Not Started'),
        sa.Column("completion_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("blocker_reason", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "production_operations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("production_job_id", sa.Integer(), sa.ForeignKey("production_jobs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default='1'),
        sa.Column("operation_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource", sa.String(100), nullable=True),
        sa.Column("work_centre_id", sa.Integer(), sa.ForeignKey("work_centres.id"), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Not Started'),
        sa.Column("depends_on_operation_id", sa.Integer(), sa.ForeignKey("production_operations.id"), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
    )
    create_table_if_missing(bind, 
        "milestones",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=True),
        sa.Column("completed_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "project_expenses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expense_code", sa.String(20), nullable=False, unique=True),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("paid_to", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "cutting_requirements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("production_job_id", sa.Integer(), sa.ForeignKey("production_jobs.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("part_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default='1'),
        sa.Column("length_mm", sa.Numeric(10, 2), nullable=False),
        sa.Column("width_mm", sa.Numeric(10, 2), nullable=False),
        sa.Column("thickness_mm", sa.Numeric(10, 2), nullable=True),
        sa.Column("grain_direction", sa.String(20), nullable=True),
        sa.Column("rotation_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("kerf_mm", sa.Numeric(6, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "client_activities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("activity_type", sa.String(30), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("logged_by", sa.String(255), nullable=True),
        sa.Column("follow_up_date", sa.DateTime(), nullable=True),
        sa.Column("follow_up_done", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    create_table_if_missing(bind, 
        "client_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("storage_backend", sa.String(20), nullable=False),
        sa.Column("drive_file_id", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "client_product_rates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("margin_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("fixed_selling_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("client_id", "product_id", name="uq_client_product_rate"),
    )
    create_table_if_missing(bind, 
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("experience", sa.String(100), nullable=True),
        sa.Column("resume_url", sa.String(500), nullable=True),
        sa.Column("resume_stored_filename", sa.String(255), nullable=True),
        sa.Column("resume_original_filename", sa.String(255), nullable=True),
        sa.Column("resume_content_type", sa.String(100), nullable=True),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default='local'),
        sa.Column("drive_file_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Applied'),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_table_if_missing(bind, 
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(10), nullable=True, unique=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("round", sa.String(50), nullable=True),
        sa.Column("scheduled_date", sa.DateTime(), nullable=False),
        sa.Column("interviewer", sa.String(255), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default='Scheduled'),
        sa.Column("overall_rating", sa.Integer(), nullable=True),
        sa.Column("technical_rating", sa.Integer(), nullable=True),
        sa.Column("communication_rating", sa.Integer(), nullable=True),
        sa.Column("culture_fit_rating", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("weaknesses", sa.Text(), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.String(20), nullable=True),
    )
    create_table_if_missing(bind, 
        "generic_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("parent_type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("storage_backend", sa.String(20), nullable=False),
        sa.Column("drive_file_id", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "units",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "stock_statuses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "stock_payment_statuses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "supplier_terms",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "task_statuses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "attendance_statuses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "machines",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "project_statuses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "priorities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "payment_modes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "lead_sources",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "project_types",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "expense_categories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "production_stages",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
    )
    create_table_if_missing(bind, 
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("module_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    create_table_if_missing(bind, 
        "id_sequences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=True),
    )

    create_index_if_missing(bind, "ix_products_product_code", "products", ["product_code"])
    create_index_if_missing(bind, "ix_products_business_id", "products", ["business_id"])
    create_index_if_missing(bind, "ix_products_name", "products", ["name"])
    create_index_if_missing(bind, "ix_products_product_type", "products", ["product_type"])
    create_index_if_missing(bind, "ix_products_category", "products", ["category"])
    create_index_if_missing(bind, "ix_products_subcategory", "products", ["subcategory"])
    create_index_if_missing(bind, "ix_locations_business_id", "locations", ["business_id"])
    create_index_if_missing(bind, "ix_locations_name", "locations", ["name"])
    create_index_if_missing(bind, "ix_locations_parent_id", "locations", ["parent_id"])
    create_index_if_missing(bind, "ix_material_categories_business_id", "material_categories", ["business_id"])
    create_index_if_missing(bind, "ix_material_categories_name", "material_categories", ["name"])
    create_index_if_missing(bind, "ix_material_subcategories_business_id", "material_subcategories", ["business_id"])
    create_index_if_missing(bind, "ix_material_subcategories_category_id", "material_subcategories", ["category_id"])
    create_index_if_missing(bind, "ix_material_subcategories_name", "material_subcategories", ["name"])
    create_index_if_missing(bind, "ix_suppliers_supplier_code", "suppliers", ["supplier_code"])
    create_index_if_missing(bind, "ix_suppliers_business_id", "suppliers", ["business_id"])
    create_index_if_missing(bind, "ix_suppliers_name", "suppliers", ["name"])
    create_index_if_missing(bind, "ix_materials_material_code", "materials", ["material_code"])
    create_index_if_missing(bind, "ix_materials_business_id", "materials", ["business_id"])
    create_index_if_missing(bind, "ix_materials_name", "materials", ["name"])
    create_index_if_missing(bind, "ix_materials_category", "materials", ["category"])
    create_index_if_missing(bind, "ix_materials_subcategory_id", "materials", ["subcategory_id"])
    create_index_if_missing(bind, "ix_materials_current_stock", "materials", ["current_stock"])
    create_index_if_missing(bind, "ix_materials_supplier_id", "materials", ["supplier_id"])
    create_index_if_missing(bind, "ix_materials_location_id", "materials", ["location_id"])
    create_index_if_missing(bind, "ix_product_materials_product_id", "product_materials", ["product_id"])
    create_index_if_missing(bind, "ix_product_materials_material_id", "product_materials", ["material_id"])
    create_index_if_missing(bind, "ix_rate_cards_rate_code", "rate_cards", ["rate_code"])
    create_index_if_missing(bind, "ix_rate_cards_business_id", "rate_cards", ["business_id"])
    create_index_if_missing(bind, "ix_rate_cards_category", "rate_cards", ["category"])
    create_index_if_missing(bind, "ix_rate_cards_subcategory", "rate_cards", ["subcategory"])
    create_index_if_missing(bind, "ix_rate_cards_item_name", "rate_cards", ["item_name"])
    create_index_if_missing(bind, "ix_clients_client_code", "clients", ["client_code"])
    create_index_if_missing(bind, "ix_clients_business_id", "clients", ["business_id"])
    create_index_if_missing(bind, "ix_clients_name", "clients", ["name"])
    create_index_if_missing(bind, "ix_clients_phone", "clients", ["phone"])
    create_index_if_missing(bind, "ix_orders_order_code", "orders", ["order_code"])
    create_index_if_missing(bind, "ix_orders_business_id", "orders", ["business_id"])
    create_index_if_missing(bind, "ix_orders_client_id", "orders", ["client_id"])
    create_index_if_missing(bind, "ix_orders_order_date", "orders", ["order_date"])
    create_index_if_missing(bind, "ix_orders_project_status", "orders", ["project_status"])
    create_index_if_missing(bind, "ix_ai_workspace_reports_order_id", "ai_workspace_reports", ["order_id"])
    create_index_if_missing(bind, "ix_report_history_report_type", "report_history", ["report_type"])
    create_index_if_missing(bind, "ix_employees_employee_code", "employees", ["employee_code"])
    create_index_if_missing(bind, "ix_employees_business_id", "employees", ["business_id"])
    create_index_if_missing(bind, "ix_employees_name", "employees", ["name"])
    create_index_if_missing(bind, "ix_employees_department", "employees", ["department"])
    create_index_if_missing(bind, "ix_users_username", "users", ["username"])
    create_index_if_missing(bind, "ix_users_email", "users", ["email"])
    create_index_if_missing(bind, "ix_users_employee_id", "users", ["employee_id"])
    create_index_if_missing(bind, "ix_notifications_business_id", "notifications", ["business_id"])
    create_index_if_missing(bind, "ix_notifications_notification_type", "notifications", ["notification_type"])
    create_index_if_missing(bind, "ix_notifications_is_read", "notifications", ["is_read"])
    create_index_if_missing(bind, "ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    create_index_if_missing(bind, "ix_notifications_dedup_key", "notifications", ["dedup_key"])
    create_index_if_missing(bind, "ix_automation_logs_rule_key", "automation_logs", ["rule_key"])
    create_index_if_missing(bind, "ix_automation_logs_status", "automation_logs", ["status"])
    create_index_if_missing(bind, "ix_automation_logs_dedup_key", "automation_logs", ["dedup_key"])
    create_index_if_missing(bind, "ix_chat_learning_candidates_phrase", "chat_learning_candidates", ["phrase"])
    create_index_if_missing(bind, "ix_chat_learning_candidates_normalized_phrase", "chat_learning_candidates", ["normalized_phrase"])
    create_index_if_missing(bind, "ix_estimates_estimate_code", "estimates", ["estimate_code"])
    create_index_if_missing(bind, "ix_estimates_business_id", "estimates", ["business_id"])
    create_index_if_missing(bind, "ix_estimates_client_id", "estimates", ["client_id"])
    create_index_if_missing(bind, "ix_estimates_order_id_unique", "estimates", ["order_id"], unique=True)
    create_index_if_missing(bind, "ix_estimates_status", "estimates", ["status"])
    create_index_if_missing(bind, "ix_estimates_parent_estimate_id", "estimates", ["parent_estimate_id"])
    create_index_if_missing(bind, "ix_estimate_line_items_estimate_id", "estimate_line_items", ["estimate_id"])
    create_index_if_missing(bind, "ix_estimate_line_items_product_id", "estimate_line_items", ["product_id"])
    create_index_if_missing(bind, "ix_order_items_order_id", "order_items", ["order_id"])
    create_index_if_missing(bind, "ix_order_items_product_id", "order_items", ["product_id"])
    create_index_if_missing(bind, "ix_order_comments_order_id", "order_comments", ["order_id"])
    create_index_if_missing(bind, "ix_payments_receipt_code", "payments", ["receipt_code"])
    create_index_if_missing(bind, "ix_payments_business_id", "payments", ["business_id"])
    create_index_if_missing(bind, "ix_payments_date", "payments", ["date"])
    create_index_if_missing(bind, "ix_payments_order_id", "payments", ["order_id"])
    create_index_if_missing(bind, "ix_payment_documents_payment_id", "payment_documents", ["payment_id"])
    create_index_if_missing(bind, "ix_payment_documents_drive_file_id", "payment_documents", ["drive_file_id"])
    create_index_if_missing(bind, "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    create_index_if_missing(bind, "ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])
    create_index_if_missing(bind, "ix_attendance_business_id", "attendance", ["business_id"])
    create_index_if_missing(bind, "ix_attendance_date", "attendance", ["date"])
    create_index_if_missing(bind, "ix_attendance_employee_id", "attendance", ["employee_id"])
    create_index_if_missing(bind, "ix_leaves_business_id", "leaves", ["business_id"])
    create_index_if_missing(bind, "ix_leaves_employee_id", "leaves", ["employee_id"])
    create_index_if_missing(bind, "ix_leaves_start_date", "leaves", ["start_date"])
    create_index_if_missing(bind, "ix_leaves_status", "leaves", ["status"])
    create_index_if_missing(bind, "ix_salary_slips_employee_id", "salary_slips", ["employee_id"])
    create_index_if_missing(bind, "ix_salary_slips_business_id", "salary_slips", ["business_id"])
    create_index_if_missing(bind, "ix_company_holidays_date", "company_holidays", ["date"])
    create_index_if_missing(bind, "ix_salary_advances_business_id", "salary_advances", ["business_id"])
    create_index_if_missing(bind, "ix_salary_advances_employee_id", "salary_advances", ["employee_id"])
    create_index_if_missing(bind, "ix_supplier_materials_supplier_id", "supplier_materials", ["supplier_id"])
    create_index_if_missing(bind, "ix_supplier_materials_material_id", "supplier_materials", ["material_id"])
    create_index_if_missing(bind, "ix_purchases_purchase_code", "purchases", ["purchase_code"])
    create_index_if_missing(bind, "ix_purchases_business_id", "purchases", ["business_id"])
    create_index_if_missing(bind, "ix_purchases_date", "purchases", ["date"])
    create_index_if_missing(bind, "ix_purchases_supplier_id", "purchases", ["supplier_id"])
    create_index_if_missing(bind, "ix_purchases_material_id", "purchases", ["material_id"])
    create_index_if_missing(bind, "ix_purchases_location_id", "purchases", ["location_id"])
    create_index_if_missing(bind, "ix_procurement_requirements_business_id", "procurement_requirements", ["business_id"])
    create_index_if_missing(bind, "ix_procurement_requirements_order_id", "procurement_requirements", ["order_id"])
    create_index_if_missing(bind, "ix_procurement_requirements_material_id", "procurement_requirements", ["material_id"])
    create_index_if_missing(bind, "ix_procurement_requirements_status", "procurement_requirements", ["status"])
    create_index_if_missing(bind, "ix_procurement_requirements_purchase_id", "procurement_requirements", ["purchase_id"])
    create_index_if_missing(bind, "ix_supplier_decisions_business_id", "supplier_decisions", ["business_id"])
    create_index_if_missing(bind, "ix_supplier_decisions_requirement_id", "supplier_decisions", ["requirement_id"])
    create_index_if_missing(bind, "ix_personal_cart_items_user_id", "personal_cart_items", ["user_id"])
    create_index_if_missing(bind, "ix_personal_cart_items_material_id", "personal_cart_items", ["material_id"])
    create_index_if_missing(bind, "ix_material_attribute_definitions_subcategory_id", "material_attribute_definitions", ["subcategory_id"])
    create_index_if_missing(bind, "ix_material_attribute_values_material_id", "material_attribute_values", ["material_id"])
    create_index_if_missing(bind, "ix_material_attribute_values_attribute_definition_id", "material_attribute_values", ["attribute_definition_id"])
    create_index_if_missing(bind, "ix_material_attribute_values_value_number", "material_attribute_values", ["value_number"])
    create_index_if_missing(bind, "ix_stock_transfers_business_id", "stock_transfers", ["business_id"])
    create_index_if_missing(bind, "ix_stock_transfers_material_id", "stock_transfers", ["material_id"])
    create_index_if_missing(bind, "ix_issues_issue_code", "issues", ["issue_code"])
    create_index_if_missing(bind, "ix_issues_date", "issues", ["date"])
    create_index_if_missing(bind, "ix_issues_order_id", "issues", ["order_id"])
    create_index_if_missing(bind, "ix_issues_material_id", "issues", ["material_id"])
    create_index_if_missing(bind, "ix_issues_location_id", "issues", ["location_id"])
    create_index_if_missing(bind, "ix_stock_adjustments_business_id", "stock_adjustments", ["business_id"])
    create_index_if_missing(bind, "ix_stock_adjustments_material_id", "stock_adjustments", ["material_id"])
    create_index_if_missing(bind, "ix_stock_adjustments_related_issue_id", "stock_adjustments", ["related_issue_id"])
    create_index_if_missing(bind, "ix_stock_adjustments_location_id", "stock_adjustments", ["location_id"])
    create_index_if_missing(bind, "ix_stock_ledger_entries_material_id", "stock_ledger_entries", ["material_id"])
    create_index_if_missing(bind, "ix_stock_ledger_entries_location_id", "stock_ledger_entries", ["location_id"])
    create_index_if_missing(bind, "ix_daily_tasks_task_code", "daily_tasks", ["task_code"])
    create_index_if_missing(bind, "ix_daily_tasks_business_id", "daily_tasks", ["business_id"])
    create_index_if_missing(bind, "ix_daily_tasks_date", "daily_tasks", ["date"])
    create_index_if_missing(bind, "ix_daily_tasks_employee_id", "daily_tasks", ["employee_id"])
    create_index_if_missing(bind, "ix_daily_tasks_order_id", "daily_tasks", ["order_id"])
    create_index_if_missing(bind, "ix_daily_tasks_order_item_id", "daily_tasks", ["order_item_id"])
    create_index_if_missing(bind, "ix_daily_tasks_status", "daily_tasks", ["status"])
    create_index_if_missing(bind, "ix_daily_tasks_parent_task_id", "daily_tasks", ["parent_task_id"])
    create_index_if_missing(bind, "ix_daily_tasks_previous_task_id", "daily_tasks", ["previous_task_id"])
    create_index_if_missing(bind, "ix_daily_tasks_due_date", "daily_tasks", ["due_date"])
    create_index_if_missing(bind, "ix_task_comments_task_id", "task_comments", ["task_id"])
    create_index_if_missing(bind, "ix_work_centres_business_id", "work_centres", ["business_id"])
    create_index_if_missing(bind, "ix_production_jobs_job_code", "production_jobs", ["job_code"])
    create_index_if_missing(bind, "ix_production_jobs_business_id", "production_jobs", ["business_id"])
    create_index_if_missing(bind, "ix_production_jobs_date", "production_jobs", ["date"])
    create_index_if_missing(bind, "ix_production_jobs_employee_id", "production_jobs", ["employee_id"])
    create_index_if_missing(bind, "ix_production_jobs_order_id", "production_jobs", ["order_id"])
    create_index_if_missing(bind, "ix_production_jobs_material_id", "production_jobs", ["material_id"])
    create_index_if_missing(bind, "ix_production_jobs_status", "production_jobs", ["status"])
    create_index_if_missing(bind, "ix_production_operations_production_job_id", "production_operations", ["production_job_id"])
    create_index_if_missing(bind, "ix_production_operations_work_centre_id", "production_operations", ["work_centre_id"])
    create_index_if_missing(bind, "ix_production_operations_status", "production_operations", ["status"])
    create_index_if_missing(bind, "ix_production_operations_employee_id", "production_operations", ["employee_id"])
    create_index_if_missing(bind, "ix_milestones_business_id", "milestones", ["business_id"])
    create_index_if_missing(bind, "ix_milestones_order_id", "milestones", ["order_id"])
    create_index_if_missing(bind, "ix_project_expenses_expense_code", "project_expenses", ["expense_code"])
    create_index_if_missing(bind, "ix_project_expenses_business_id", "project_expenses", ["business_id"])
    create_index_if_missing(bind, "ix_project_expenses_date", "project_expenses", ["date"])
    create_index_if_missing(bind, "ix_project_expenses_order_id", "project_expenses", ["order_id"])
    create_index_if_missing(bind, "ix_cutting_requirements_business_id", "cutting_requirements", ["business_id"])
    create_index_if_missing(bind, "ix_cutting_requirements_production_job_id", "cutting_requirements", ["production_job_id"])
    create_index_if_missing(bind, "ix_cutting_requirements_product_id", "cutting_requirements", ["product_id"])
    create_index_if_missing(bind, "ix_cutting_requirements_material_id", "cutting_requirements", ["material_id"])
    create_index_if_missing(bind, "ix_client_activities_client_id", "client_activities", ["client_id"])
    create_index_if_missing(bind, "ix_client_activities_date", "client_activities", ["date"])
    create_index_if_missing(bind, "ix_client_activities_follow_up_date", "client_activities", ["follow_up_date"])
    create_index_if_missing(bind, "ix_client_documents_client_id", "client_documents", ["client_id"])
    create_index_if_missing(bind, "ix_client_documents_drive_file_id", "client_documents", ["drive_file_id"])
    create_index_if_missing(bind, "ix_client_product_rates_client_id", "client_product_rates", ["client_id"])
    create_index_if_missing(bind, "ix_client_product_rates_product_id", "client_product_rates", ["product_id"])
    create_index_if_missing(bind, "ix_candidates_business_id", "candidates", ["business_id"])
    create_index_if_missing(bind, "ix_candidates_name", "candidates", ["name"])
    create_index_if_missing(bind, "ix_candidates_drive_file_id", "candidates", ["drive_file_id"])
    create_index_if_missing(bind, "ix_candidates_status", "candidates", ["status"])
    create_index_if_missing(bind, "ix_interviews_business_id", "interviews", ["business_id"])
    create_index_if_missing(bind, "ix_interviews_candidate_id", "interviews", ["candidate_id"])
    create_index_if_missing(bind, "ix_interviews_scheduled_date", "interviews", ["scheduled_date"])
    create_index_if_missing(bind, "ix_interviews_status", "interviews", ["status"])
    create_index_if_missing(bind, "ix_generic_documents_parent_type", "generic_documents", ["parent_type"])
    create_index_if_missing(bind, "ix_generic_documents_parent_id", "generic_documents", ["parent_id"])
    create_index_if_missing(bind, "ix_generic_documents_drive_file_id", "generic_documents", ["drive_file_id"])
    create_index_if_missing(bind, "ix_units_name", "units", ["name"])
    create_index_if_missing(bind, "ix_stock_statuses_name", "stock_statuses", ["name"])
    create_index_if_missing(bind, "ix_stock_payment_statuses_name", "stock_payment_statuses", ["name"])
    create_index_if_missing(bind, "ix_supplier_terms_name", "supplier_terms", ["name"])
    create_index_if_missing(bind, "ix_departments_name", "departments", ["name"])
    create_index_if_missing(bind, "ix_task_statuses_name", "task_statuses", ["name"])
    create_index_if_missing(bind, "ix_attendance_statuses_name", "attendance_statuses", ["name"])
    create_index_if_missing(bind, "ix_machines_name", "machines", ["name"])
    create_index_if_missing(bind, "ix_project_statuses_name", "project_statuses", ["name"])
    create_index_if_missing(bind, "ix_priorities_name", "priorities", ["name"])
    create_index_if_missing(bind, "ix_payment_modes_name", "payment_modes", ["name"])
    create_index_if_missing(bind, "ix_lead_sources_name", "lead_sources", ["name"])
    create_index_if_missing(bind, "ix_project_types_name", "project_types", ["name"])
    create_index_if_missing(bind, "ix_expense_categories_name", "expense_categories", ["name"])
    create_index_if_missing(bind, "ix_production_stages_name", "production_stages", ["name"])
    create_index_if_missing(bind, "ix_audit_logs_id", "audit_logs", ["id"])
    create_index_if_missing(bind, "ix_audit_logs_module_name", "audit_logs", ["module_name"])
    create_index_if_missing(bind, "ix_audit_logs_created_at", "audit_logs", ["created_at"])

    create_index_if_missing(bind, 
        "ux_payments_cash_reference_number", "payments", ["reference_number"], unique=True,
        postgresql_where=sa.text("reference_number LIKE 'CASH-%'"),
        sqlite_where=sa.text("reference_number LIKE 'CASH-%'"),
    )

def downgrade() -> None:
    """Deliberately unsupported - this is the baseline representing
    Woodful's current schema. A downgrade from here has nothing
    meaningful to revert to (down_revision is None) and, per explicit
    instruction, must never risk dropping a production database by
    accident. If a genuine need to tear down a database built from
    this baseline arises (e.g. a disposable local/test database),
    drop it directly rather than through this migration."""
    raise NotImplementedError(
        "Downgrading past the baseline is not supported. This revision "
        "represents Woodful's current schema floor - there is nothing "
        "before it to revert to, and no destructive downgrade is provided "
        "to avoid ever accidentally dropping a production database."
    )
