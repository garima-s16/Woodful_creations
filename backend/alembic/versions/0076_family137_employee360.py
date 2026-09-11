"""Family 137 (updated requirement) - Employee 360 / HR Command Center
(section 13, subsections 13.1-13.17).

Adds:
  - employees.exit_date / exit_reason - offboarding facts (section
    13.9). Nullable, meaningless until an employee actually leaves;
    every existing row is unaffected.
  - generic_documents.document_type / issue_date / expiry_date -
    lets the existing shared document vault (already used by orders,
    suppliers, purchases, products, and employees - see
    app.modules.documents.api.GenericDocument) carry the categorized,
    expiry-aware metadata section 13.8 (Employee Document Vault) asks
    for, without creating an employee-only parallel document table.
    Benefits every parent type, not just employees.
  - employee_lifecycle_items - the onboarding/offboarding checklist
    section 13.9 asks for ("actionable onboarding checklist ... show
    progress based on actual completion"). One row per checklist item
    per employee per phase. Some items are computed live from
    existing data at read time (record created, documents submitted,
    role assigned, manager assigned) rather than stored here at all -
    this table only holds the items that have no other authoritative
    source (contract completed, access setup, equipment assigned,
    policies acknowledged, training completed, initial review
    completed, and the offboarding equivalents), matching this
    project's "do not create duplicate data stores merely to connect
    these areas" rule.

Idempotent, using this project's existing shared migration guards
(create_table_if_missing/add_column_if_missing/create_index_if_missing
in app.platform.database), matching 0073/0074/0075's established
convention.

Forward-only for the same reason as 0074/0075: purely additive, no
prior state to revert to.
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database import create_table_if_missing, create_index_if_missing, add_column_if_missing


revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    add_column_if_missing(bind, "employees", sa.Column("exit_date", sa.DateTime(), nullable=True))
    add_column_if_missing(bind, "employees", sa.Column("exit_reason", sa.Text(), nullable=True))

    add_column_if_missing(bind, "generic_documents", sa.Column("document_type", sa.String(50), nullable=True))
    add_column_if_missing(bind, "generic_documents", sa.Column("issue_date", sa.Date(), nullable=True))
    add_column_if_missing(bind, "generic_documents", sa.Column("expiry_date", sa.Date(), nullable=True))

    create_table_if_missing(
        bind, "employee_lifecycle_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),  # "onboarding" | "offboarding"
        sa.Column("item_key", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_date", sa.DateTime(), nullable=True),
        sa.Column("completed_by", sa.String(255), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    create_index_if_missing(bind, "ix_employee_lifecycle_items_employee_id", "employee_lifecycle_items", ["employee_id"])
    create_index_if_missing(
        bind, "ux_employee_lifecycle_items_employee_phase_key", "employee_lifecycle_items",
        ["employee_id", "phase", "item_key"], unique=True,
    )


def downgrade() -> None:
    """Forward-only - see module docstring."""
    raise NotImplementedError(
        "Migration 0076 is forward-only. See this module's docstring for why a "
        "blind downgrade here would risk dropping data it did not create."
    )
