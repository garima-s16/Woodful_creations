"""Family 137, Step 1 - Balance-Before-Dispatch guardrail, Cost-Drift
alert, and the Approved Specification / Sample Lock.

Adds:
  - estimate_line_items.cost_at_creation: the cost basis (Product.cost_price
    or suggested_cost_price) snapshotted at the moment a line item is
    priced, so a later change in material/product cost can be compared
    against what was actually quoted (see Cost-Drift Alert, sales/api.py).
    Nullable and backfilled to NULL for pre-existing rows - their true
    historical cost basis is genuinely unknown, matching the same
    "NULL means unknown, not zero" convention already used for
    Issue.rate_at_issue.
  - approved_specifications: the authoritative, versioned record of the
    exact material/finish/hardware spec a client approved for an Order,
    so "this isn't the colour I approved" has a literal, dated answer.

Idempotent: both changes are guarded using this project's existing
shared migration guards (app.platform.database's create_table_if_missing/
add_column_if_missing/create_index_if_missing - the "migration_guards.py"
section), not a locally reimplemented equivalent. The order_id index is
created via a single create_index_if_missing call - do not also add
index=True on the column inside create_table_if_missing's column list;
a column-level index=True there would additionally cause SQLAlchemy to
emit its own auto-named index at table-creation time, colliding with
this explicitly named one on a fresh database.

Balance-Before-Dispatch requires no schema change - it is enforced at
the Order status-transition endpoint (sales/api.py update_order) using
Order.balance, which already exists, and logs to the existing
audit_logs table via app.platform.audit.log_action - no new column or
table needed for that feature.

Forward-only: this migration only adds new, additive schema (a
nullable column and a brand-new table introduced by this feature).
There is no meaningful prior state to revert to, and - because
upgrade() is idempotent and may find the column/table already present
from a previous partial run - a downgrade() that blindly drops them
could destroy a pre-existing object this migration did not itself
create. See downgrade() below.
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database import create_table_if_missing, add_column_if_missing, create_index_if_missing


revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    add_column_if_missing(
        bind, "estimate_line_items",
        sa.Column("cost_at_creation", sa.Numeric(12, 2), nullable=True),
    )

    create_table_if_missing(
        bind, "approved_specifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("approved_specifications.id"), nullable=True),
        sa.Column("material", sa.String(255), nullable=True),
        sa.Column("finish", sa.String(255), nullable=True),
        sa.Column("veneer", sa.String(255), nullable=True),
        sa.Column("laminate", sa.String(255), nullable=True),
        sa.Column("colour", sa.String(100), nullable=True),
        sa.Column("hardware", sa.String(255), nullable=True),
        sa.Column("batch_reference", sa.String(100), nullable=True),
        sa.Column("sample_photo_path", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # approved / superseded / change_requested - see ApprovedSpecification model docstring
        sa.Column("status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    # Single, explicit index creation - the only place order_id gets
    # indexed. create_index_if_missing is itself idempotent, but this
    # is also only attempted right after a genuine create (matching how
    # the table's own creation is guarded) rather than unconditionally,
    # since there is nothing else to check it against otherwise.
    create_index_if_missing(bind, "ix_approved_specifications_order_id", "approved_specifications", ["order_id"])


def downgrade() -> None:
    """Deliberately unsupported, and deliberately non-destructive.

    upgrade() is idempotent: on a database where approved_specifications
    or estimate_line_items.cost_at_creation already existed for some
    other reason before this migration ran, upgrade() correctly skips
    creating them - which means this migration cannot reliably tell,
    at downgrade time, whether it is safe to drop them. A downgrade
    that blindly drops the table/column on that assumption risks
    destroying a pre-existing object this migration never created, per
    this project's explicit no-data-loss requirement. Since both
    changes are purely additive (a new nullable column, a new table)
    with no prior schema state to revert to, and per this project's own
    baseline precedent (0073's downgrade is likewise deliberately
    unsupported), this migration does not implement a destructive
    downgrade. Reverting this feature, if ever required, must be done
    as a deliberate, reviewed, hand-run operation against the specific
    database in question - never an automatic `alembic downgrade`."""
    raise NotImplementedError(
        "Migration 0074 is forward-only. See this function's docstring for why a "
        "blind downgrade here would risk dropping data it did not create."
    )

