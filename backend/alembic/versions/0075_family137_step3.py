"""Family 137, Step 3 - shared secure-link infrastructure for the
Client Approval Hub (feature 1) and My Order link (feature 3).

Adds:
  - client_access_tokens - see app.modules.clients.models.ClientAccessToken
    for the full design rationale (mirrors PasswordResetToken's hash-only
    storage, but not single-use).
  - estimates.approved_by / approved_at / client_decision_comments -
    the authoritative record of a client's decision made through the
    portal (see app.modules.sales.models.Estimate and
    clients/portal_api.py).

Idempotent, using this project's existing shared migration guards
(create_table_if_missing/add_column_if_missing/create_index_if_missing
in app.platform.database), matching 0073/0074's established convention.

Forward-only for the same reason as 0074: purely additive, no prior
state to revert to, and upgrade() may correctly skip creation on a
database that already has this table from an earlier partial run - a
downgrade cannot then safely tell what it would and would not be
destroying.
"""
from alembic import op
import sqlalchemy as sa
from app.platform.database import create_table_if_missing, create_index_if_missing, add_column_if_missing


revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_table_if_missing(
        bind, "client_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    create_index_if_missing(
        bind, "ux_client_access_tokens_token_hash", "client_access_tokens", ["token_hash"], unique=True,
    )
    create_index_if_missing(
        bind, "ix_client_access_tokens_subject", "client_access_tokens", ["subject_type", "subject_id"],
    )

    add_column_if_missing(bind, "estimates", sa.Column("approved_by", sa.String(255), nullable=True))
    add_column_if_missing(bind, "estimates", sa.Column("approved_at", sa.DateTime(), nullable=True))
    add_column_if_missing(bind, "estimates", sa.Column("client_decision_comments", sa.Text(), nullable=True))


def downgrade() -> None:
    """Forward-only - see module docstring."""
    raise NotImplementedError(
        "Migration 0075 is forward-only. See this module's docstring for why a "
        "blind downgrade here would risk dropping data it did not create."
    )
