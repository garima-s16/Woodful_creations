"""Add an index on orders.priority.

Context (audit section 12 - database/index review, done after
implementing the Orders workspace search, Clients search, and the
centralized active-order/open-estimate filters in this same change
set): GET /api/orders/, GET /api/orders/workspace, and the Orders
Excel export (app/modules/sales/api.py) all filter with
Order.priority == <value> when a priority dropdown value is selected -
the exact same equality-filter shape project_status already has its
own index for - but priority itself had no index of its own before
this migration. Declared at the ORM level too (Order.priority's Column,
now index=True) so a fresh Base.metadata.create_all()/test database
gets it for free, matching the "model declares it, this migration is
what an existing already-provisioned database needs" split every other
index in this chain (0078, 0079) already follows.

Deliberately NOT added in this pass: indexes for the new Orders
workspace `search` param (order_code, business_id, Client.name,
Client.client_code) or the expanded Clients `search` param (name,
client_code, business_id, phone, alternate_phone, email,
contact_person). Both search filters use `ilike(f"%term%")` -
leading-wildcard substring matching - which a plain B-tree index
(SQLite or Postgres) cannot use at all; order_code/business_id/
client_code already carry unique indexes from their own column
definitions that support exact lookups but not substring search, and
a real substring-search index (Postgres pg_trgm/GIN) would be a
Postgres-only extension dependency this codebase does not otherwise
take on, would not work against the SQLite path this same code must
also run against, and is not justified by anything in this audit -
adding it here would be exactly the "random/redundant index" section
12 says not to add.

Forward-only in the sense that downgrade() simply drops the index -
no data-reconciliation step, so this is safe to reverse.
"""
from alembic import op
from app.platform.database import create_index_if_missing, index_exists


revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    create_index_if_missing(
        bind, "ix_orders_priority", "orders", ["priority"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, "orders", "ix_orders_priority"):
        op.drop_index("ix_orders_priority", table_name="orders")
